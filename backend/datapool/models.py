from datetime import datetime, timezone

from datapool.connection import Base
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship


def utc_now():
    return datetime.now(timezone.utc)


class Skill(Base):
    __tablename__ = "skills"

    skill_id = Column(String(50), primary_key=True)
    skill_type = Column(String(50), nullable=False)
    skill_title = Column(String(255), nullable=False)
    skill_intro = Column(Text, nullable=True)

    skill_quests = relationship(
        "SkillQuest",
        back_populates="skill",
        cascade="all, delete-orphan",
    )

    skill_holders = relationship(
        "SkillHolder",
        back_populates="skill",
        cascade="all, delete-orphan",
    )




class Quest(Base):
    __tablename__ = "quests"

    quest_id = Column(String(100), primary_key=True)

    # Order of the quest in its generated sequence
    seq_no = Column(Integer, nullable=False, default=1)

    # Match the existing PostgreSQL column names
    quest_title = Column(String(255), nullable=False)
    quest_intro = Column(Text, nullable=True)

    quest_type = Column(
        String(30),
        nullable=False,
        default="Learning",
    )
    scale = Column(
        String(20),
        nullable=False,
        default="others",
    )

    quest_metrics = Column(Float, nullable=False, default=0.0)
    template = Column(Text, nullable=True)

    last_update = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    # Always store duration in milliseconds
    duration_ms = Column(
        Integer,
        nullable=False,
        default=172800000,
    )

    skill_quests = relationship(
        "SkillQuest",
        back_populates="quest",
        cascade="all, delete-orphan",
    )



class SkillQuest(Base):
    __tablename__ = "skill_quests"

    skill_id = Column(
        String(50),
        ForeignKey("skills.skill_id", ondelete="CASCADE"),
        primary_key=True,
    )

    quest_id = Column(
        String(100),
        ForeignKey("quests.quest_id", ondelete="CASCADE"),
        primary_key=True,
    )

    skill = relationship("Skill", back_populates="skill_quests")
    quest = relationship("Quest", back_populates="skill_quests")


class SkillHolder(Base):
    __tablename__ = "skill_holders"

    skill_id = Column(
        String(50),
        ForeignKey("skills.skill_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # User records are stored in a separate database.
    # Therefore, user_id intentionally has no cross-database FK.
    user_id = Column(String(50), primary_key=True)

    skill = relationship("Skill", back_populates="skill_holders")


class URLRecord(Base):
    __tablename__ = "urls"

    url_id = Column(String(100), primary_key=True)
    url = Column(Text, nullable=False)
    is_visited = Column(String(3), nullable=False, default="No")