
import os

import httpx


def ping_agent_service() -> dict:
    """Check whether the separate agent service is reachable."""
    agent_url = os.getenv(
        "AGENT_SERVICE_URL",
        "http://127.0.0.1:8001",
    ).rstrip("/")

    try:
        response = httpx.get(
            f"{agent_url}/",
            timeout=3.0,
        )
        response.raise_for_status()
        return {
            "status": "connected",
            "message": "Agent service is reachable.",
        }
    except httpx.HTTPError as exc:
        print(f"Agent service is not reachable yet: {exc}")
        return {
            "status": "unavailable",
            "message": "Backend started, but agent service is not reachable.",
        }

def trigger_main_agent(
    update_id: str,
    user_id: str,
    action_required: str,
) -> dict:
    
    """
    Placeholder for the Main Agent workflow.
    Replace this implementation with the actual agent call later.
    """
    return {
        "status": "accepted",
        "message": "Main Agent trigger received (placeholder).",
        "update_id": update_id,
        "user_id": user_id,
        "action_required": action_required,
    }
