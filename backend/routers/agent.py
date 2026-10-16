from agents.main_agent import trigger_main_agent as run_main_agent
from database.models import User
from fastapi import APIRouter, Depends, HTTPException
from schemas.agent import MainAgentTriggerRequest

from routers.auth import get_current_user

router = APIRouter(
    prefix="/agents/main-agent",
    tags=["Main Agent"],
)


@router.post("/trigger")
def trigger_main_agent(
    request: MainAgentTriggerRequest,
    current_user: User = Depends(get_current_user),
):
    if request.user_id != current_user.user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot trigger the agent for another user.",
        )

    return run_main_agent(
        update_id=request.update_id,
        user_id=current_user.user_id,
        action_required=request.action_required,
    )