from database.connection import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.types import JSON


class User(Base):
    __tablename__ = "users"


    user_id = Column(String(50), primary_key=True)
    username = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)

    interests = Column(JSON, nullable=False, default=list)

    summary = Column(Text, nullable=True)
    occupation = Column(String(150), nullable=True)
    experience = Column(Text, nullable=True)
    education_status = Column(String(100), nullable=True)
    education_summary = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class UserLog(Base):
  

    __tablename__ = "user_logs"

    log_id = Column(String(50), primary_key=True)
    user_id = Column(String(50),nullable=False,index=True)

    log_desc = Column(Text, nullable=False)
    action_required = Column(Boolean, nullable=False, default=False)
    timestamp = Column(DateTime(timezone=True),nullable=False,server_default=func.now(),index=True)


class RecentLog(Base):


    __tablename__ = "recent_logs"

    log_id = Column(String(50), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)

    log_desc = Column(Text, nullable=False)
    action_required = Column(Boolean, nullable=False, default=False)

    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class UserSkill(Base):
    """
    Relational link between a user and a skill in the DataPool.
    skill_id is validated by the application because the DataPool
    is in a separate PostgreSQL database.
    """

    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50),nullable=False,index=True)
    skill_id = Column(String(50),nullable=False,index=True)
    acquired_at = Column(DateTime(timezone=True),nullable=False,server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "skill_id",
            name="uq_user_skill",
        ),
    )


class UserQuest(Base):
    """
    Relational link between a user and a quest in the DataPool.
    One row tracks the user's progress on one quest.
    """

    __tablename__ = "user_quests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50),nullable=False,index=True)
    quest_id = Column(String(50),nullable=False,index=True)

    status = Column(String(20),nullable=False,default="active",server_default="active")
    started_at = Column(DateTime(timezone=True),nullable=False,server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "quest_id",
            name="uq_user_quest",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'failed')",
            name="ck_user_quest_status",
        ),
        Index(
            "ix_user_quests_status_started",
            "status",
            "started_at",
        ),
    )