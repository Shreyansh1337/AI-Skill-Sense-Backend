from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    username: str
    email: EmailStr
    age: int | None = None
    gender: str | None = None
    interests: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    active_quests: list[str] = Field(default_factory=list)
    completed_quest: list[str] = Field(default_factory=list)
    failed_quests: list[str] = Field(default_factory=list)
    summary: str | None = None
    occupation: str | None = None
    experience: str | None = None
    education_status: str | None = None
    education_summary: str | None = None


class UserLogResponse(BaseModel):
    user_id : str
    log_id: str
    log_desc: str
    action_required: str
    timestamp: datetime


class UserLogsResponse(BaseModel):
    logs: list[UserLogResponse]


class UserAssignmentRequest(BaseModel):
    assignment_type: Literal["Skill", "Quest"]
    item_id: str = Field(min_length=1, max_length=100)


class UserAssignmentResponse(BaseModel):
    status: Literal["assigned", "already_assigned"]
    user_id: str
    assignment_type: Literal["Skill", "Quest"]
    item_id: str
