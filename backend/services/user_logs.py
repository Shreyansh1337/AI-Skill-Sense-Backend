from uuid import NAMESPACE_URL, uuid4, uuid5

from agents.main_agent import trigger_main_agent
from database.models import UserLog
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

ACTION_REQUIRED_ACTIVITY_TYPES = {
    "new_skill",
    "new_profile",
    "profile_update",
    "quest_completion",
}


def create_user_log(
    db: Session,
    background_tasks: BackgroundTasks,
    user_id: str,
    activity_type: str,
    log_desc: str,
    event_id: str | None = None,
) -> UserLog:
    log_id = (
        str(uuid5(NAMESPACE_URL, f"ai-skill-sense:{user_id}:{event_id}"))
        if event_id
        else str(uuid4())
    )
    existing_log = db.query(UserLog).filter(UserLog.log_id == log_id).first()
    if existing_log is not None:
        return existing_log

    log = UserLog(
        log_id=log_id,
        user_id=user_id,
        log_desc=log_desc,
        action_required=activity_type.strip().lower()
        in ACTION_REQUIRED_ACTIVITY_TYPES,
    )
    db.add(log)

    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise

    background_tasks.add_task(
        trigger_main_agent,
        update_id=log.log_id,
        user_id=log.user_id,
        action_required="Yes" if log.action_required else "No",
    )
    return log
