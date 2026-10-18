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

import ipaddress
from urllib.parse import urlparse

router = APIRouter(
    prefix="/api/urls",
    tags=["URLs"],
)

logger = logging.getLogger(__name__)

def is_valid_target_url(url_str: str) -> bool:
    try:
        parsed = urlparse(url_str)
        
        # 1. Ensure valid web schemes
        if parsed.scheme not in ("http", "https"):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False

        hostname_lower = hostname.lower()

        # 2. Block localhost, loopbacks, and container host aliases
        blocked_hostnames = {
            "localhost", 
            "127.0.0.1", 
            "0.0.0.0", 
            "::1", 
            "host.docker.internal",
            "gateway.docker.internal"
        }
        if hostname_lower in blocked_hostnames:
            return False

        # 3. Block internal/local TLDs
        if hostname_lower.endswith((".local", ".internal", ".test", ".localhost", ".lan", ".corp")):
            return False

        # 4. Block private/internal IP ranges (SSRF protection)
        try:
            ip = ipaddress.ip_address(hostname)
            if (
                ip.is_private 
                or ip.is_loopback 
                or ip.is_link_local 
                or ip.is_reserved 
                or ip.is_multicast
            ):
                return False
        except ValueError:
            # Not a raw IP address (it's a domain name like example.com), which is allowed dynamically!
            pass

        return True
    except Exception:
        return False

def dispatch_next_unvisited_url() -> None:
    # 1. Open a short-lived session strictly to claim the next unvisited URL
    db = SessionLocal()
    url_id = None
    url_str = None
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

        # Mark as visited immediately and commit to release the row lock & connection
        url_record.is_visited = "Yes"
        url_id = url_record.url_id
        url_str = url_record.url
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to claim the next unvisited URL.")
        return
    finally:
        db.close()  # Connection is returned to the pool instantly!

    # 2. Run the long extractor workflow completely outside of the database session
    if url_id and url_str:
        try:
            result = trigger_extractor(url_id, url_str)
            if result.get("status") != "success":
                logger.error(f"Extractor did not complete URL {url_id}.")
        except Exception:
            logger.exception(f"Error executing extractor for URL {url_id}.")
            
@router.post("/dispatch-next", status_code=status.HTTP_202_ACCEPTED)
def dispatch_next_url(
    background_tasks: BackgroundTasks,
):
    """
    Unprotected manual nudge endpoint to trigger the next queued URL processing task.
    """
    background_tasks.add_task(dispatch_next_unvisited_url)
    return {"status": "accepted", "message": "URL dispatch has been queued successfully."}


@router.post("/process", response_model=URLProcessResponse)
def process_url(
    request: URLProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_datapool_db),
    _current_user: User | None = Depends(get_current_user),
):
    url = str(request.url)
    
    # Filter out invalid, internal, or non-whitelisted URLs
    if not is_valid_target_url(url):
        logger.warning(f"Blocked untrusted or internal URL attempt: {url}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL is blocked (internal addresses or non-whitelisted domains are not permitted)."
        )

    existing_url = db.query(URLRecord).filter(URLRecord.url == url).first()

    if existing_url:
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