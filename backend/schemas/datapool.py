
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
