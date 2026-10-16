from pydantic import BaseModel, Field


class MainAgentTriggerRequest(BaseModel):
    update_id: str
    user_id: str
    action_required: str = Field(pattern="^(Yes|No)$")
