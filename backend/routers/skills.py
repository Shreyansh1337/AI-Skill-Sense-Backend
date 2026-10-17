from uuid import uuid4

from agents.main_agent import trigger_quest_maker_in_background
from database.models import User
from datapool.dependencies import get_datapool_db
from datapool.models import Quest, Skill, SkillHolder, SkillQuest
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from schemas.datapool import (
    SkillAllocationRequest,
    SkillAllocationResponse,
    SkillByTypeRequest,
    SkillCreateRequest,
    SkillCreateResponse,
    SkillResponse,
    SkillsByTypeResponse,
    SkillUpdateRequest,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from routers.auth import get_current_user, require_agent_secret

router = APIRouter(prefix="/api/skills",tags=["Skills"])

@router.post("/by-type", response_model=SkillsByTypeResponse)
def get_skills_by_type(
    request: SkillByTypeRequest,
    db: Session = Depends(get_datapool_db),
    _current_user: User | None = Depends(get_current_user),
):
    
    skills = (db.query(Skill.skill_id, Skill.skill_intro).filter(Skill.skill_type == request.skill_type).all())

    return {
        "skills": [
            {
                "skill_id": skill_id,
                "skill_intro": skill_intro or "",
            }
            for skill_id, skill_intro in skills
        ]
    }


@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill_by_id(
    skill_id: str,
    db: Session = Depends(get_datapool_db),
    _current_user: User | None = Depends(get_current_user),
):
    skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()

    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill_holder_ids = [
        holder.user_id
        for holder in db.query(SkillHolder).filter(
            SkillHolder.skill_id == skill_id
        ).all()
    ]

    related_quest_ids = [
        relation.quest_id
        for relation in db.query(SkillQuest).filter(
            SkillQuest.skill_id == skill_id
        ).all()
    ]

    return {
        "skill_id": skill.skill_id,
        "skill_type": skill.skill_type,
        "skill_title": skill.skill_title,
        "skill_intro": skill.skill_intro or "",
        "skill_holder_id": skill_holder_ids,
        "related_quest_id": related_quest_ids,
    }


@router.put("/{skill_id}", response_model=SkillResponse)
def update_skill(
    skill_id: str,
    request: SkillUpdateRequest,
    db: Session = Depends(get_datapool_db),
    current_user: User = Depends(get_current_user),
):
    skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()

    if skill is None:
        raise HTTPException(status_code=404, detail="Sikll not found")

    update_data = request.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(skill, field, value)

    db.commit()
    db.refresh(skill)

    skill_holder_ids = [
        holder.user_id
        for holder in db.query(SkillHolder).filter(
            SkillHolder.skill_id == skill_id
        ).all()
    ]

    related_quest_ids = [
        relation.quest_id
        for relation in db.query(SkillQuest).filter(
            SkillQuest.skill_id == skill_id
        ).all()
    ]

    return {
        "skill_id": skill.skill_id,
        "skill_type": skill.skill_type,
        "skill_title": skill.skill_title,
        "skill_intro": skill.skill_intro or "",
        "skill_holder_id": skill_holder_ids,
        "related_quest_id": related_quest_ids,
    }


@router.post("/create", response_model=SkillCreateResponse)
def create_skill(
    request: SkillCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_datapool_db),
    _current_user: User | None = Depends(get_current_user),
):
    if request.skill_type not in {
        "Technical", "Fitness", "Finance", "Communication"
    }:
        raise HTTPException(status_code=422,detail="Invalid skill type")
    
    for quest_id in request.related_quest_id:
        quest = db.query(Quest).filter(Quest.quest_id == quest_id).first()

        if quest is None:
            raise HTTPException(status_code=404,detail=f"Quest not found: {quest_id}",)

    skill_id = request.skill_id or str(uuid4())
    if db.query(Skill).filter(Skill.skill_id == skill_id).first():
        raise HTTPException(
            status_code=409,
            detail="A skill with this skill_id already exists.",
        )

    skill = Skill(
        skill_id=skill_id,
        skill_type=request.skill_type,
        skill_title=request.skill_title,
        skill_intro=request.skill_intro,
    )

    try:
        db.add(skill)
        db.flush()

        for user_id in set(request.skill_holder_id):
            holder = SkillHolder(skill_id=skill_id,user_id=user_id)
            db.add(holder)

        for quest_id in set(request.related_quest_id):
            relation = SkillQuest(skill_id=skill_id,quest_id=quest_id)
            db.add(relation)

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A skill with this skill_id already exists.",
        )
    except Exception:
        db.rollback()
        raise

    background_tasks.add_task(trigger_quest_maker_in_background, skill_id)
    return {"skill_id": skill_id}


@router.post("/{skill_id}/generate-quests", status_code=202)
def retry_quest_maker(
    skill_id: str,
    background_tasks: BackgroundTasks,
    _agent_secret: None = Depends(require_agent_secret),
):
    background_tasks.add_task(trigger_quest_maker_in_background, skill_id)
    return {
        "status": "accepted",
        "message": "Quest Maker has been queued for this skill.",
        "skill_id": skill_id,
    }