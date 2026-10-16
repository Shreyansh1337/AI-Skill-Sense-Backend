
from agents.main_agent import trigger_main_agent as run_main_agent
from fastapi import APIRouter
from schemas.agent import MainAgentTriggerRequest

router = APIRouter(
    prefix="/agents/main-agent",
    tags=["Main Agent"],
)


@router.post("/trigger")
def trigger_main_agent(request: MainAgentTriggerRequest):
    return run_main_agent(
        update_id=request.update_id,
        user_id=request.user_id,
        action_required=request.action_required,
    )
