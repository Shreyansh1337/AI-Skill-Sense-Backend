from datetime import datetime, timezone

from database.connection import Base
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True)
    username = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)
    interests = Column(JSON, nullable=False, default=list)

    summary = Column(Text, nullable=True)
    occupation = Column(String(255), nullable=True)
    experience = Column(Text, nullable=True)
    education_status = Column(String(100), nullable=True)
    education_summary = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class UserLog(Base):
    __tablename__ = "user_logs"

    log_id = Column(String(100), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    log_desc = Column(Text, nullable=False)
    action_required = Column(Boolean, nullable=False, default=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )


class UserWebhookCredential(Base):
    __tablename__ = "user_webhook_credentials"

    user_id = Column(String(50), primary_key=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class HealthConnectPairing(Base):
    __tablename__ = "health_connect_pairings"

    code_hash = Column(String(64), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)


class HealthConnectDevice(Base):
    __tablename__ = "health_connect_devices"

    user_id = Column(String(50), primary_key=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    device_name = Column(String(100), nullable=False)
    linked_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)


class HealthConnectRecord(Base):
    __tablename__ = "health_connect_records"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_record_id",
            name="uq_health_connect_user_record",
        ),
    )

    record_id = Column(String(100), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    source_record_id = Column(String(255), nullable=False)
    record_type = Column(String(40), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(40), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class RecentLog(Base):
    __tablename__ = "recent_logs"

    log_id = Column(String(100), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    log_desc = Column(Text, nullable=False)
    action_required = Column(Boolean, nullable=False, default=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )


class UserSkill(Base):
    __tablename__ = "user_skills"

    user_id = Column(String(50), primary_key=True)
    skill_id = Column(String(50), primary_key=True)

    acquired_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )



class UserQuest(Base):
    __tablename__ = "user_quests"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "quest_id",
            name="uq_user_quest",
        ),
        CheckConstraint(
            "progress >= 0.0 AND progress <= 1.0",
            name="ck_user_quest_progress_range",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'failed')",
            name="ck_user_quest_status",
        ),
    )

    # Match the existing PostgreSQL primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    user_id = Column(String(50), nullable=False, index=True)
    quest_id = Column(String(100), nullable=False, index=True)

    # Duration is stored in milliseconds
    duration_ms = Column(Integer, nullable=True)

    # Independent progress for each user's assignment: 0.0 to 1.0
    progress = Column(Float, nullable=False, default=0.0)

    status = Column(String(20), nullable=False, default="active")

    # allocation_time in the API contract maps to started_at
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    completed_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
