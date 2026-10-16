
from database.dependencies import get_db
from database.models import User, UserLog, UserQuest, UserSkill
from fastapi import APIRouter, Depends, HTTPException
from schemas.user import UserLogsResponse, UserProfileResponse
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)



@router.get("/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(user_id: str,db: Session = Depends(get_db),):

    user = db.query(User).filter(User.user_id == user_id).first()

    if user is None:
        raise HTTPException(status_code=404,detail="User not found")
    
    skills = (db.query(UserSkill.skill_id).filter(UserSkill.user_id == user_id).all())
    quests = (db.query(UserQuest.quest_id, UserQuest.status).filter(UserQuest.user_id == user_id).all())

    skill_ids = [skill_id for (skill_id,) in skills]
    active_quests = [quest_id for quest_id, status in quests if status == "active"]
    completed_quests = [quest_id for quest_id, status in quests if status == "completed"]
    failed_quests = [quest_id for quest_id, status in quests if status == "failed"]
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "age": user.age,
        "gender": user.gender,
        "interests": user.interests or [],
        "skills": skill_ids,
        "active_quests": active_quests ,
        "completed_quest": completed_quests ,
        "failed_quests": failed_quests ,
        "summary": user.summary,
        "occupation": user.occupation,
        "experience": user.experience,
        "education_status": user.education_status,
        "education_summary": user.education_summary,
    }

@router.get("/{user_id}/logs", response_model=UserLogsResponse)
def get_user_logs(user_id: str,limit: int = 25,db: Session = Depends(get_db)):
    logs = (
        db.query(UserLog)
        .filter(UserLog.user_id == user_id)
        .order_by(UserLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    return {
        "logs": [
            {
                "user_id": log.user_id,
                "log_id": log.log_id,
                "log_desc": log.log_desc,
                "action_required": "Yes" if log.action_required else "No",
                "timestamp": log.timestamp,
            }
            for log in logs
        ]
    }

    


