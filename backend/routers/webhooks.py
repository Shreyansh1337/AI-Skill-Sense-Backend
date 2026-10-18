import hashlib
import os
import secrets

from database.dependencies import get_db
from database.models import User, UserWebhookCredential, utc_now
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from schemas.integrations import (
    GenericWebhookEvent,
    WebhookCredentialResponse,
    WebhookSettingsResponse,
)
from schemas.user import ActivityWebhookRequest, UserLogResponse
from services.user_logs import create_user_log
from sqlalchemy.orm import Session

from routers.auth import get_current_user, require_agent_secret

router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"],
)


def _require_signed_in_user(current_user: User | None) -> User:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A user access token is required.",
        )
    return current_user


@router.post(
    "/activities",
    response_model=UserLogResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_agent_secret)],
)
def receive_activity(
    request: ActivityWebhookRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    log = create_user_log(
        db,
        background_tasks,
        user.user_id,
        request.activity_type,
        request.log_desc,
        request.event_id,
    )
    return {
        "user_id": log.user_id,
        "log_id": log.log_id,
        "log_desc": log.log_desc,
        "action_required": "Yes" if log.action_required else "No",
        "timestamp": log.timestamp,
    }


@router.get("/me", response_model=WebhookSettingsResponse)
def get_webhook_settings(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    user = _require_signed_in_user(current_user)
    credential = (
        db.query(UserWebhookCredential)
        .filter(UserWebhookCredential.user_id == user.user_id)
        .first()
    )
    return {
        "configured": credential is not None,
        "created_at": credential.created_at if credential else None,
    }


@router.put("/me", response_model=WebhookCredentialResponse)
def rotate_webhook_credential(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    user = _require_signed_in_user(current_user)
    token = secrets.token_urlsafe(32)
    credential = (
        db.query(UserWebhookCredential)
        .filter(UserWebhookCredential.user_id == user.user_id)
        .first()
    )
    if credential is None:
        credential = UserWebhookCredential(
            user_id=user.user_id,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        )
        db.add(credential)
    else:
        credential.token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()
        credential.created_at = utc_now()

    try:
        db.commit()
        db.refresh(credential)
    except Exception:
        db.rollback()
        raise

    public_api_base_url = os.getenv("PUBLIC_API_BASE_URL")
    base_url = (
        public_api_base_url.rstrip("/")
        if public_api_base_url
        else str(request.base_url).rstrip("/")
    )
    webhook_url = f"{base_url}/api/webhooks/external/{token}"
    return {
        "webhook_url": webhook_url,
        "created_at": credential.created_at,
    }


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def revoke_webhook_credential(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    user = _require_signed_in_user(current_user)
    credential = (
        db.query(UserWebhookCredential)
        .filter(UserWebhookCredential.user_id == user.user_id)
        .first()
    )
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No external webhook is configured.",
        )
    db.delete(credential)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.post(
    "/external/{token}",
    response_model=UserLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def receive_external_activity(
    token: str,
    request: GenericWebhookEvent,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    credential = (
        db.query(UserWebhookCredential)
        .filter(UserWebhookCredential.token_hash == token_hash)
        .first()
    )
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found.",
        )

    log = create_user_log(
        db,
        background_tasks,
        credential.user_id,
        request.activity_type,
        request.log_desc,
        request.event_id,
    )
    return {
        "user_id": log.user_id,
        "log_id": log.log_id,
        "log_desc": log.log_desc,
        "action_required": "Yes" if log.action_required else "No",
        "timestamp": log.timestamp,
    }
