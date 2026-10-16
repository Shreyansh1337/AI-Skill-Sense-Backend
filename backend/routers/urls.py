from uuid import uuid4

from database.models import User
from datapool.dependencies import get_datapool_db
from datapool.models import URLRecord
from fastapi import APIRouter, Depends, HTTPException
from schemas.url import (
    URLGetIDRequest,
    URLGetIDResponse,
    URLProcessRequest,
    URLProcessResponse,
)
from sqlalchemy.orm import Session

from routers.auth import get_current_user

router = APIRouter(
    prefix="/api/urls",
    tags=["URLs"],
)


@router.post("/process", response_model=URLProcessResponse)
def process_url(
    request: URLProcessRequest,
    db: Session = Depends(get_datapool_db),
    current_user: User = Depends(get_current_user),
):
    url = str(request.url)

    existing_url = db.query(URLRecord).filter(URLRecord.url == url).first()

    if existing_url:
        return {"url": url}

    new_url = URLRecord(
        url_id=str(uuid4()),
        url=url,
        is_visited=False,
    )

    try:
        db.add(new_url)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"url": url}



@router.post("/get-id", response_model=URLGetIDResponse)
def get_url_id(
    request: URLGetIDRequest,
    db: Session = Depends(get_datapool_db),
):
    url = str(request.url)

    existing_url = db.query(URLRecord).filter(URLRecord.url == url).first()

    if existing_url is None:
        
        raise HTTPException(status_code=404,detail="URL not found in DataPool",)

    return {"url_id": existing_url.url_id}
