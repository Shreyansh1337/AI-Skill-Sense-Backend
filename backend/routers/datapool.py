
from datapool.dependencies import get_datapool_db
from datapool.models import Skill
from fastapi import APIRouter, Depends
from schemas.datapool import (
    SkillAllocationRequest,
    SkillAllocationResponse,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/datapool", tags=["DataPool"])


@router.post("/skills/allocate",response_model=SkillAllocationResponse)
def allocate_skills(
    request: SkillAllocationRequest,
    db: Session = Depends(get_datapool_db),
):

    query = db.query(Skill)

    if request.excluded_skill_ids:
        query = query.filter(Skill.skill_id.in_(request.excluded_skill_ids))

    if request.keywords:
        keyword_filters = [Skill.skill_title.ilike(f"%{keyword}%")| Skill.skill_intro.ilike(f"%{keyword}%")
            for keyword in request.keywords
        ]

        query = query.filter(*keyword_filters)

    skills = query.order_by(Skill.skill_title).limit(request.limit).all()

    return {
        "skill_ids": [skill.skill_id for skill in skills]
    }

