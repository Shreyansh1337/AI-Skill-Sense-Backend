from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import os
import httpx
import logging
import time


logger = logging.getLogger(__name__)
MAIN_AGENT_MAX_ATTEMPTS = 5
MAIN_AGENT_RETRYABLE_STATUSES = {429, 503}
MAIN_AGENT_RETRYABLE_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout)
MAIN_AGENT_CONNECT_TIMEOUT_SECONDS = 300.0
MAIN_AGENT_READ_TIMEOUT_SECONDS = 300.0
MAIN_AGENT_RETRY_DELAY_CAP_SECONDS = 300


def _backoff_delay(attempt: int) -> float:
    return min(5 * (2 ** attempt), MAIN_AGENT_RETRY_DELAY_CAP_SECONDS)


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(
                max(float(retry_after), 0),
                MAIN_AGENT_RETRY_DELAY_CAP_SECONDS,
            )
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return min(
                    max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0),
                    MAIN_AGENT_RETRY_DELAY_CAP_SECONDS,
                )
            except (TypeError, ValueError, OverflowError):
                logger.warning("Agent returned an invalid Retry-After header.")
    return _backoff_delay(attempt)


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
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            logger.warning(
                "Agent service is reachable but rate-limited its startup health check."
            )
            return {
                "status": "rate_limited",
                "message": "Agent service responded to the health check with HTTP 429.",
            }
        logger.warning("Agent service health check failed: %s", exc)
        return {
            "status": "unavailable",
            "message": "Backend started, but agent service is not reachable.",
        }
    except httpx.HTTPError as exc:
        logger.warning("Agent service is not reachable yet: %s", exc)
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

    endpoint = f"{agent_url}/agents/main-agent/trigger"
    for attempt in range(MAIN_AGENT_MAX_ATTEMPTS):
        try:
            response = httpx.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=httpx.Timeout(
                    MAIN_AGENT_READ_TIMEOUT_SECONDS,
                    connect=MAIN_AGENT_CONNECT_TIMEOUT_SECONDS,
                    write=30.0,
                    pool=10.0,
                ),
            )
        except MAIN_AGENT_RETRYABLE_ERRORS as exc:
            if attempt + 1 == MAIN_AGENT_MAX_ATTEMPTS:
                raise RuntimeError(
                    "Failed to communicate with the Main Agent service after "
                    f"{MAIN_AGENT_MAX_ATTEMPTS} attempts."
                ) from exc
            delay = _backoff_delay(attempt)
            logger.warning(
                "Main Agent request failed transiently; retrying in %.0f "
                "seconds (attempt %d/%d): %s",
                delay,
                attempt + 2,
                MAIN_AGENT_MAX_ATTEMPTS,
                exc,
            )
            time.sleep(delay)
            continue
        except httpx.HTTPError as exc:
            raise RuntimeError(
                "Failed to communicate with the Main Agent service."
            ) from exc

        if (
            response.status_code in MAIN_AGENT_RETRYABLE_STATUSES
            and attempt + 1 < MAIN_AGENT_MAX_ATTEMPTS
        ):
            delay = _retry_delay(response, attempt)
            logger.warning(
                "Main Agent returned HTTP %d; retrying in %.0f seconds "
                "(attempt %d/%d, server=%s, render_id=%s, cf_ray=%s, "
                "retry_after=%s).",
                response.status_code,
                delay,
                attempt + 2,
                MAIN_AGENT_MAX_ATTEMPTS,
                response.headers.get("Server", "unknown"),
                response.headers.get("rndr-id", "unavailable"),
                response.headers.get("CF-Ray", "unavailable"),
                response.headers.get("Retry-After", "unavailable"),
            )
            time.sleep(delay)
            continue

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if response.status_code in MAIN_AGENT_RETRYABLE_STATUSES:
                logger.error(
                    "Main Agent exhausted retries after HTTP %d "
                    "(server=%s, render_id=%s, cf_ray=%s, retry_after=%s).",
                    response.status_code,
                    response.headers.get("Server", "unknown"),
                    response.headers.get("rndr-id", "unavailable"),
                    response.headers.get("CF-Ray", "unavailable"),
                    response.headers.get("Retry-After", "unavailable"),
                )
            raise RuntimeError(
                "Main Agent service returned HTTP "
                f"{response.status_code} after {attempt + 1} attempt(s)."
            ) from exc
        try:
            agent_response = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Main Agent service returned invalid JSON after a successful response."
            ) from exc
        return {
            "status": "success",
            "message": "Main Agent triggered successfully.",
            "agent_response": agent_response,
        }

    raise RuntimeError("Main Agent trigger exhausted retries without a response.")


def trigger_main_agent_in_background(
    update_id: str,
    user_id: str,
    action_required: str,
) -> None:
    try:
        trigger_main_agent(update_id, user_id, action_required)
    except RuntimeError as exc:
        logger.error(
            "Main Agent nudge failed after retries for update_id=%s "
            "user_id=%s: %s",
            update_id,
            user_id,
            exc,
        )


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