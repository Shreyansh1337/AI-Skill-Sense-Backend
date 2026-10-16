from uuid import uuid4

from datapool.dependencies import get_datapool_db
from datapool.models import Quest, Skill, SkillHolder, SkillQuest
from fastapi import APIRouter, Depends, HTTPException
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
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/skills",tags=["Skills"])

@router.post("/by-type", response_model=SkillsByTypeResponse)
def get_skills_by_type(request: SkillByTypeRequest,db: Session= Depends(get_datapool_db)):
    
    skills = (db.query(Skill.skill_id, Skill.skill_intro).filter(Skill.skill_type == request.skill_type).all())

    return {
        "skills": [
            {
                "skill_id": skill_id,
                "skill_intro": skill_intro,
            }
            for skill_id, skill_intro in skills
        ]
    }


@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill_by_id(
    skill_id: str,
    db: Session = Depends(get_datapool_db),
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
        "skill_intro": skill.skill_intro,
        "skill_holder_id": skill_holder_ids,
        "related_quest_id": related_quest_ids,
    }


@router.put("/{skill_id}", response_model=SkillResponse)
def update_skill(
    skill_id: str,
    request: SkillUpdateRequest,
    db: Session = Depends(get_datapool_db),
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
        "skill_intro": skill.skill_intro,
        "skill_holder_id": skill_holder_ids,
        "related_quest_id": related_quest_ids,
    }


@router.post("/create", response_model=SkillCreateResponse)
def create_skill(
    request: SkillCreateRequest,
    db: Session = Depends(get_datapool_db),
):
    if request.skill_type not in {
        "Technical", "Fitness", "Finance", "Communication"
    }:
        raise HTTPException(status_code=422,detail="Invalid skill type")
    
    for quest_id in request.related_quest_id:
        quest = db.query(Quest).filter(Quest.quest_id == quest_id).first()

        if quest is None:
            raise HTTPException(status_code=404,detail=f"Quest not found: {quest_id}",)

    skill_id = str(uuid4())

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

    except Exception:
        db.rollback()
        raise

    return {"skill_id": skill_id}







