from database.dependencies import get_db
from database.models import User
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from schemas.user import ActivityWebhookRequest, UserLogResponse
from services.user_logs import create_user_log
from sqlalchemy.orm import Session

from routers.auth import require_agent_secret

router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"],
)


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
