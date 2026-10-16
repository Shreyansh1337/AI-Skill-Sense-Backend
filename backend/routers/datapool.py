
from datapool.dependencies import get_datapool_db
from datapool.models import Quest, Skill
from fastapi import APIRouter, Depends
from schemas.datapool import (
    QuestAllocationRequest,
    QuestAllocationResponse,
    SkillAllocationRequest,
    SkillAllocationResponse,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/datapool", tags=["DataPool"])



@router.post("/skills/allocate", response_model=SkillAllocationResponse)
def allocate_skills(
    request: SkillAllocationRequest,
    db: Session = Depends(get_datapool_db),
):
    # Start with all available skills.
    query = db.query(Skill)

    # exclduing users owned skills
    if request.excluded_skill_ids:
        query = query.filter(
            ~Skill.skill_id.in_(request.excluded_skill_ids)
        )

    # Try keyword matching first.
    if request.keywords:
        keyword_filters = [
            Skill.skill_title.ilike(f"%{keyword}%")
            | Skill.skill_intro.ilike(f"%{keyword}%")
            for keyword in request.keywords
        ]
        matching_skills = (
            query.filter(*keyword_filters)
            .order_by(Skill.skill_title)
            .limit(request.limit)
            .all()
        )

        # returning matching skill even if 1 matches
        if matching_skills:
            return {
                "skill_ids": [
                    skill.skill_id for skill in matching_skills
                ]
            }

    #if no match then return first "limit" skills
    skills = query.order_by(Skill.skill_title).limit(request.limit).all()

    return {"skill_ids": [skill.skill_id for skill in skills]}


@router.post("/quests/allocate", response_model=QuestAllocationResponse)
def allocate_quests(
    request: QuestAllocationRequest,
    db: Session = Depends(get_datapool_db),
):
    # Start with all available quests.
    query = db.query(Quest)

    # Exclude user completed/active quest
    if request.excluded_quest_ids:
        query = query.filter(
            ~Quest.quest_id.in_(request.excluded_quest_ids)
        )

    # Try keyword matching first.
    if request.keywords:
        keyword_filters = [
            Quest.quest_title.ilike(f"%{keyword}%")
            | Quest.quest_intro.ilike(f"%{keyword}%")
            for keyword in request.keywords
        ]
        matching_quests = (
            query.filter(*keyword_filters)
            .order_by(Quest.quest_title)
            .limit(request.limit)
            .all()
        )

        # returning matching quest
        if matching_quests:
            return {
                "quest_ids": [
                    quest.quest_id for quest in matching_quests
                ]
            }

    # No match then first "limit" eligible quest
    quests = query.order_by(Quest.quest_title).limit(request.limit).all()

    return {"quest_ids": [quest.quest_id for quest in quests]}
