from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from fastapi import BackgroundTasks
from database.models import HealthConnectRecord, UserQuest
from datapool.models import Quest
from schemas.integrations import HealthConnectRecordUpload
from sqlalchemy.orm import Session
from sqlalchemy import func

from services.user_logs import create_user_log

HEALTH_RECORD_TYPES = {
    "steps": "count",
    "active_calories": "kcal",
    "distance": "m",
    "exercise": "s",
    "heart_rate": "bpm",
}

SCALE_ALIASES = {
    "step": ("steps", "count"),
    "steps": ("steps", "count"),
    "count": ("steps", "count"),
    "calorie": ("active_calories", "kcal"),
    "calories": ("active_calories", "kcal"),
    "kcal": ("active_calories", "kcal"),
    "kilocalorie": ("active_calories", "kcal"),
    "kilocalories": ("active_calories", "kcal"),
    "activecalories": ("active_calories", "kcal"),
    "activecaloriesburned": ("active_calories", "kcal"),
    "m": ("distance", "m"),
    "meter": ("distance", "m"),
    "meters": ("distance", "m"),
    "km": ("distance", "km"),
    "kilometer": ("distance", "km"),
    "kilometers": ("distance", "km"),
    "mi": ("distance", "mi"),
    "mile": ("distance", "mi"),
    "miles": ("distance", "mi"),
    "s": ("exercise", "s"),
    "sec": ("exercise", "s"),
    "second": ("exercise", "s"),
    "seconds": ("exercise", "s"),
    "min": ("exercise", "min"),
    "minute": ("exercise", "min"),
    "minutes": ("exercise", "min"),
    "h": ("exercise", "h"),
    "hr": ("exercise", "h"),
    "hour": ("exercise", "h"),
    "hours": ("exercise", "h"),
    "bpm": ("heart_rate", "bpm"),
    "beatsperminute": ("heart_rate", "bpm"),
}


def _normalize_scale(scale: str) -> str:
    return "".join(character for character in scale.lower() if character.isalnum())


def _record_value_in_scale(record: HealthConnectRecord, scale: str) -> float | None:
    normalized_scale = _normalize_scale(scale)
    mapping = SCALE_ALIASES.get(normalized_scale)
    if mapping is None or mapping[0] != record.record_type:
        return None

    if record.record_type == "distance":
        source_unit = record.unit.lower()
        meters = record.value
        if source_unit in {"km", "kilometer", "kilometers"}:
            meters *= 1000
        elif source_unit in {"mi", "mile", "miles"}:
            meters *= 1609.344
        elif source_unit not in {"m", "meter", "meters"}:
            return None

        if mapping[1] == "km":
            return meters / 1000
        if mapping[1] == "mi":
            return meters / 1609.344
        return meters

    if record.record_type == "exercise":
        source_unit = record.unit.lower()
        seconds = record.value
        if source_unit in {"min", "minute", "minutes"}:
            seconds *= 60
        elif source_unit in {"h", "hr", "hour", "hours"}:
            seconds *= 3600
        elif source_unit not in {"s", "sec", "second", "seconds"}:
            return None

        if mapping[1] == "min":
            return seconds / 60
        if mapping[1] == "h":
            return seconds / 3600
        return seconds

    if record.unit.lower() != mapping[1]:
        return None
    return record.value


def update_matching_quest_progress(
    db: Session,
    datapool_db: Session,
    user_id: str,
) -> tuple[int, list[str]]:
    active_assignments = (
        db.query(UserQuest)
        .filter(UserQuest.user_id == user_id, UserQuest.status == "active")
        .all()
    )
    if not active_assignments:
        return 0, []

    quest_ids = {assignment.quest_id for assignment in active_assignments}
    quests = {
        quest.quest_id: quest
        for quest in datapool_db.query(Quest)
        .filter(
            Quest.quest_id.in_(quest_ids),
            func.lower(Quest.quest_type) == "physical",
        )
        .all()
    }
    if not quests:
        return 0, []

    earliest_start = min(
        assignment.started_at
        for assignment in active_assignments
    )
    if earliest_start.tzinfo is None:
        earliest_start = earliest_start.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    records = (
        db.query(HealthConnectRecord)
        .filter(
            HealthConnectRecord.user_id == user_id,
            HealthConnectRecord.record_type.in_(
                set(HEALTH_RECORD_TYPES)
            ),
            HealthConnectRecord.start_time >= earliest_start,
            HealthConnectRecord.start_time <= now,
        )
        .all()
    )
    updated_count = 0
    completed_quest_ids: list[str] = []

    for assignment in active_assignments:
        quest = quests.get(assignment.quest_id)
        if quest is None or quest.quest_metrics <= 0:
            continue

        scale = quest.scale
        if _normalize_scale(scale) not in SCALE_ALIASES:
            continue

        started_at = assignment.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        duration_ms = assignment.duration_ms or quest.duration_ms
        deadline = started_at + timedelta(milliseconds=duration_ms)

        matching_records = []
        for record in records:
            record_start = record.start_time
            if record_start.tzinfo is None:
                record_start = record_start.replace(tzinfo=timezone.utc)
            if started_at <= record_start <= min(deadline, now):
                value = _record_value_in_scale(record, scale)
                if value is not None:
                    matching_records.append((record, value))

        scale_unit = SCALE_ALIASES[_normalize_scale(scale)][1]
        if scale_unit == "bpm":
            measured_value = max((value for _, value in matching_records), default=0.0)
        else:
            measured_value = sum(value for _, value in matching_records)

        progress = min(1.0, measured_value / quest.quest_metrics)
        if progress <= assignment.progress:
            continue

        assignment.progress = progress
        assignment.updated_at = now
        updated_count += 1
        if progress >= 1.0:
            assignment.status = "completed"
            assignment.completed_at = now
            completed_quest_ids.append(assignment.quest_id)

    return updated_count, completed_quest_ids


def save_health_sync(
    db: Session,
    datapool_db: Session,
    background_tasks: BackgroundTasks,
    user_id: str,
    records: list[HealthConnectRecordUpload],
) -> dict[str, int]:
    inserted = 0
    updated = 0
    activity_logs: list[tuple[str, str, float, str]] = []
    latest_records = {
        payload.record_id: payload
        for payload in records
    }

    try:
        for payload in latest_records.values():
            if _record_value_in_scale_from_payload(payload) is None:
                raise ValueError(
                    f"Unsupported unit {payload.unit!r} for "
                    f"{payload.record_type} Health Connect data."
                )

            existing = (
                db.query(HealthConnectRecord)
                .filter(
                    HealthConnectRecord.user_id == user_id,
                    HealthConnectRecord.source_record_id == payload.record_id,
                )
                .first()
            )
            if existing is None:
                existing = HealthConnectRecord(
                    record_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"health-connect:{user_id}:{payload.record_id}",
                        )
                    ),
                    user_id=user_id,
                    source_record_id=payload.record_id,
                    record_type=payload.record_type,
                    value=payload.value,
                    unit=payload.unit,
                    start_time=payload.start_time,
                    end_time=payload.end_time,
                )
                db.add(existing)
                inserted += 1
            else:
                existing.record_type = payload.record_type
                existing.value = payload.value
                existing.unit = payload.unit
                existing.start_time = payload.start_time
                existing.end_time = payload.end_time
                existing.updated_at = datetime.now(timezone.utc)
                updated += 1

            activity_logs.append(
                (
                    payload.record_id,
                    payload.record_type,
                    payload.value,
                    payload.unit,
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    quest_progress_updates, completed_quest_ids = update_matching_quest_progress(
        db,
        datapool_db,
        user_id,
    )
    if completed_quest_ids:
        for quest_id in completed_quest_ids:
            create_user_log(
                db,
                background_tasks,
                user_id,
                "quest_completion",
                f"Completed Physical quest {quest_id} using Health Connect data.",
                event_id=f"health-connect-quest-completion:{quest_id}",
            )
    else:
        db.commit()

    for record_id, record_type, value, unit in activity_logs:
        create_user_log(
            db,
            background_tasks,
            user_id,
            "health_activity",
            f"Health Connect recorded {record_type}: {value:g} {unit}.",
            event_id=(
                "health-connect:"
                f"{sha256(record_id.encode('utf-8')).hexdigest()}"
            ),
        )

    return {
        "inserted": inserted,
        "updated": updated,
        "quest_progress_updates": quest_progress_updates,
    }


def _record_value_in_scale_from_payload(
    payload: HealthConnectRecordUpload,
) -> float | None:
    expected = HEALTH_RECORD_TYPES.get(payload.record_type)
    if expected is None:
        return None

    probe = HealthConnectRecord(
        record_id="validation",
        user_id="validation",
        source_record_id="validation",
        record_type=payload.record_type,
        value=payload.value,
        unit=payload.unit,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    if payload.record_type in {"distance", "exercise"}:
        return _record_value_in_scale(probe, expected)
    if payload.unit.lower() != expected:
        return None
    return payload.value
