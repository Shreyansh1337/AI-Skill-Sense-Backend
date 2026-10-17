import logging
from uuid import uuid4

from agents.main_agent import trigger_extractor
from datapool.connection import SessionLocal
from database.models import User
from datapool.dependencies import get_datapool_db
from datapool.models import URLRecord
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from schemas.url import (
    URLGetIDRequest,
    URLGetIDResponse,
    URLProcessRequest,
    URLProcessResponse,
)
from sqlalchemy.orm import Session

from routers.auth import get_current_user, require_agent_secret

router = APIRouter(
    prefix="/api/urls",
    tags=["URLs"],
)

logger = logging.getLogger(__name__)


def dispatch_next_unvisited_url() -> None:
    db = SessionLocal()
    try:
        url_record = (
            db.query(URLRecord)
            .filter(URLRecord.is_visited == "No")
            .order_by(URLRecord.url_id)
            .with_for_update(skip_locked=True)
            .first()
        )
        if url_record is None:
            db.rollback()
            return

        result = trigger_extractor(url_record.url_id, url_record.url)
        if result.get("status") != "success":
            raise RuntimeError(
                f"Extractor did not complete URL {url_record.url_id}."
            )

        url_record.is_visited = "Yes"
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to dispatch the next unvisited URL.")
    finally:
        db.close()


@router.post("/process", response_model=URLProcessResponse)
def process_url(
    request: URLProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_datapool_db),
    _current_user: User | None = Depends(get_current_user),
):
    url = str(request.url)

    existing_url = db.query(URLRecord).filter(URLRecord.url == url).first()

    if existing_url:
        if existing_url.is_visited != "Yes":
            background_tasks.add_task(dispatch_next_unvisited_url)
        return {"url": url}

    # Fixed state consistency: use string "No" instead of boolean False to match URLRecord model
    new_url = URLRecord(
        url_id=str(uuid4()),
        url=url,
        is_visited="No",
    )

    try:
        db.add(new_url)
        db.commit()
    except Exception:
        db.rollback()
        raise

    background_tasks.add_task(dispatch_next_unvisited_url)
    return {"url": url}


@router.post("/get-id", response_model=URLGetIDResponse)
def get_url_id(
    request: URLGetIDRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_datapool_db),
    _current_user: User | None = Depends(get_current_user),
):
    """
    Looks up a URL ID. If the discovered URL does not exist yet,
    it automatically registers it as unvisited ("No") to fix incomplete discovery.
    Authenticated users and the internal agent can look up or register URLs.
    """
    url = str(request.url)

    existing_url = db.query(URLRecord).filter(URLRecord.url == url).first()

    # Fixed discovery behavior: create the record automatically if missing
    if existing_url is None:
        existing_url = URLRecord(
            url_id=str(uuid4()),
            url=url,
            is_visited="No",
        )
        try:
            db.add(existing_url)
            db.commit()
            db.refresh(existing_url)
        except Exception:
            db.rollback()
            raise

    if existing_url.is_visited != "Yes":
        background_tasks.add_task(dispatch_next_unvisited_url)

    return {"url_id": existing_url.url_id}


@router.post("/dispatch-next", status_code=status.HTTP_202_ACCEPTED)
def dispatch_next_url(
    background_tasks: BackgroundTasks,
    _agent_secret: None = Depends(require_agent_secret),
):
    background_tasks.add_task(dispatch_next_unvisited_url)
    return {"status": "accepted", "message": "URL dispatch has been queued."}