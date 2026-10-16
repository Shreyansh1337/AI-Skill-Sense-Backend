
from datetime import datetime, timezone

from database.models import User
from datapool.dependencies import get_datapool_db
from datapool.models import Quest, Skill, SkillQuest
from fastapi import APIRouter, Depends, HTTPException
from schemas.datapool import (
    QuestAllocationRequest,
    QuestAllocationResponse,
    QuestCreateRequest,
    QuestCreateResponse,
    SkillAllocationRequest,
    SkillAllocationResponse,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from routers.auth import get_current_user

router = APIRouter(prefix="/api/datapool", tags=["DataPool"])


@router.post("/skills/allocate", response_model=SkillAllocationResponse)
def allocate_skills(
    request: SkillAllocationRequest,
    db: Session = Depends(get_datapool_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Skill)

    if request.excluded_skill_ids:
        query = query.filter(
            ~Skill.skill_id.in_(request.excluded_skill_ids)
        )

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

        if matching_skills:
            return {
                "skill_ids": [
                    skill.skill_id for skill in matching_skills
                ]
            }

    skills = query.order_by(Skill.skill_title).limit(request.limit).all()

    return {"skill_ids": [skill.skill_id for skill in skills]}


@router.post("/quests/allocate", response_model=QuestAllocationResponse)
def allocate_quests(
    request: QuestAllocationRequest,
    db: Session = Depends(get_datapool_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Quest)

    if request.excluded_quest_ids:
        query = query.filter(
            ~Quest.quest_id.in_(request.excluded_quest_ids)
        )

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

        if matching_quests:
            return {
                "quest_ids": [
                    quest.quest_id for quest in matching_quests
                ]
            }

    quests = query.order_by(Quest.quest_title).limit(request.limit).all()

    return {"quest_ids": [quest.quest_id for quest in quests]}


@router.post("/quests/create", response_model=QuestCreateResponse)
def create_quest(
    request: QuestCreateRequest,
    db: Session = Depends(get_datapool_db),
    current_user: User = Depends(get_current_user),
):
    existing_quest = (
        db.query(Quest)
        .filter(Quest.quest_id == request.quest_id)
        .first()
    )

    if existing_quest:
        raise HTTPException(
            status_code=409,
            detail="A quest with this quest_id already exists.",
        )

    linked_skills = set(request.linked_skill)

    if linked_skills:
        existing_skill_ids = {
            skill_id
            for (skill_id,) in (
                db.query(Skill.skill_id)
                .filter(Skill.skill_id.in_(linked_skills))
                .all()
            )
        }

        missing_skills = linked_skills - existing_skill_ids

        if missing_skills:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown skill IDs: {sorted(missing_skills)}",
            )

    # The agent's duration unit must be seconds for this conversion.
    duration_ms = round(request.duration * 1000)

    if duration_ms <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quest duration must be positive.",
        )

    quest = Quest(
        quest_id=request.quest_id,
        seq_no=request.seq_no,
        quest_title=request.quest_name,
        quest_intro=request.quest_desc,
        quest_type=request.quest_type,
        scale=request.scale,
        quest_metrics=request.quest_metrics,
        template=request.template,
        last_update=request.last_update or datetime.now(timezone.utc),
        duration_ms=duration_ms,
    )

    try:
        db.add(quest)
        db.flush()

        for skill_id in linked_skills:
            db.add(
                SkillQuest(
                    skill_id=skill_id,
                    quest_id=request.quest_id,
                )
            )

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The quest could not be created because of a database constraint.",
        )

    except Exception:
        db.rollback()
        raise

    return QuestCreateResponse(
        quest_id=quest.quest_id,
        message="Quest created successfully.",
    )
