import os
import httpx
import logging


logger = logging.getLogger(__name__)


def _agent_headers() -> dict[str, str]:
    secret = os.getenv("AGENT_SECRET_KEY")
    if not secret:
        raise RuntimeError("AGENT_SECRET_KEY is not configured.")
    return {"X-Agent-Secret": secret}


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
    Dispatches the main agent trigger payload to the separate LangGraph agent service
    using an HTTP POST request and the internal AGENT_SECRET_KEY for authentication.
    """
    agent_url = os.getenv(
        "AGENT_SERVICE_URL",
        "http://127.0.0.1:8001",
    ).rstrip("/")

    agent_secret_key = os.getenv("AGENT_SECRET_KEY")

    if not agent_secret_key:
        raise RuntimeError("AGENT_SECRET_KEY is not configured.")
    headers = {"X-Agent-Secret": agent_secret_key}

    payload = {
        "update_id": update_id,
        "user_id": user_id,
        "action_required": action_required,
    }

    try:
        response = httpx.post(
            f"{agent_url}/agents/main-agent/trigger",
            json=payload,
            headers=headers,
            timeout=300.0,
        )
        response.raise_for_status()
        return {
            "status": "success",
            "message": "Main Agent triggered successfully.",
            "agent_response": response.json(),
        }
    except httpx.HTTPError as exc:
        logger.exception("Failed to trigger Main Agent service.")
        raise RuntimeError("Failed to communicate with the agent service.") from exc


def trigger_extractor(url_id: str, url: str) -> dict:
    agent_url = os.getenv(
        "AGENT_SERVICE_URL",
        "http://127.0.0.1:8001",
    ).rstrip("/")
    response = httpx.post(
        f"{agent_url}/agents/extractor/trigger",
        json={"url_id": url_id, "url": url, "is_visited": "No"},
        headers=_agent_headers(),
        timeout=300.0,
    )
    response.raise_for_status()
    return response.json()


def trigger_quest_maker(skill_id: str) -> dict:
    agent_url = os.getenv(
        "AGENT_SERVICE_URL",
        "http://127.0.0.1:8001",
    ).rstrip("/")
    response = httpx.post(
        f"{agent_url}/agents/quest-maker/trigger",
        json={"skill_id": skill_id},
        headers=_agent_headers(),
        timeout=300.0,
    )
    response.raise_for_status()
    return response.json()


def trigger_quest_maker_in_background(skill_id: str) -> None:
    try:
        trigger_quest_maker(skill_id)
    except (httpx.HTTPError, RuntimeError):
        logger.exception(
            "Could not trigger Quest Maker for newly created skill %s.",
            skill_id,
        )