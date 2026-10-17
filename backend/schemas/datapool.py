
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_id: str
    skill_type: str
    skill_title: str
    skill_intro: str
    skill_holder_id: list[str] = Field(default_factory=list)
    related_quest_id: list[str] = Field(default_factory=list)


class QuestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quest_id: str
    quest_title: str
    quest_intro: str
    duration_ms: int


class SkillByTypeRequest(BaseModel):
    skill_type: str


class SkillUpdateRequest(BaseModel):
    skill_type: str | None = None
    skill_title: str | None = None
    skill_intro: str | None = None


class SkillCreateRequest(BaseModel):
    skill_id: str | None = Field(default=None, min_length=1, max_length=50)
    skill_type: str
    skill_title: str
    skill_intro: str
    skill_holder_id: list[str] = Field(default_factory=list)
    related_quest_id: list[str] = Field(default_factory=list)


class SkillCreateResponse(BaseModel):
    skill_id: str


class SkillsByTypeResponse(BaseModel):
    skills: list[dict[str, str]]


class SkillAllocationRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    excluded_skill_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=100)


class SkillAllocationResponse(BaseModel):
    skill_ids: list[str] = Field(default_factory=list)


class QuestAllocationRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    excluded_quest_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=100)


class QuestAllocationResponse(BaseModel):
    quest_ids: list[str] = Field(default_factory=list)


class QuestCreateRequest(BaseModel):
    quest_id: str = Field(min_length=1, max_length=100)
    seq_no: int = Field(default=1, ge=1)
    linked_skill: list[str] = Field(default_factory=list)
    quest_name: str = Field(min_length=1, max_length=255)
    quest_desc: str = ""
    quest_type: str = Field(default="Learning", max_length=30)
    scale: str = Field(default="others", max_length=20)
    quest_metrics: float = Field(default=0.0, ge=0)
    template: str = ""
    last_update: datetime | None = None
    duration: float = Field(gt=0)
    quest_holder_id: list[str] = Field(default_factory=list)


class QuestCreateResponse(BaseModel):
    quest_id: str
    message: str
