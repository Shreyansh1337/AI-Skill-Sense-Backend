from datapool.connection import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)


class Skill(Base):
    __tablename__ = "skills"

    skill_id = Column(String(50), primary_key=True)

    skill_type = Column(String(30), nullable=False, index=True)
    skill_title = Column(String(200), nullable=False)
    skill_intro = Column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "skill_type IN ('Technical', 'Fitness', 'Finance', 'Communication')",
            name="ck_skill_type",
        ),
    )


class Quest(Base):
    __tablename__ = "quests"

    quest_id = Column(String(50), primary_key=True)
    quest_title = Column(String(200), nullable=False)
    quest_intro = Column(Text, nullable=False)


    duration_ms = Column(Integer, nullable=False, default=172800000)

    __table_args__ = (
        CheckConstraint(
            "duration_ms > 0",
            name="ck_quest_duration_positive",
        ),
    )


class SkillQuest(Base):
    """
    Relational link between a skill and its related quests.
    Replaces the related_quest_id array in the stored schema.
    """

    __tablename__ = "skill_quests"

    id = Column(Integer, primary_key=True, autoincrement=True)

    skill_id = Column(String(50),ForeignKey("skills.skill_id", ondelete="CASCADE"),nullable=False,index=True)
    quest_id = Column(String(50),ForeignKey("quests.quest_id", ondelete="CASCADE"),nullable=False,index=True)

    __table_args__ = (
        UniqueConstraint(
            "skill_id",
            "quest_id",
            name="uq_skill_quest",
        ),
    )


class SkillHolder(Base):

    __tablename__ = "skill_holders"

    id = Column(Integer, primary_key=True, autoincrement=True)

    skill_id = Column(String(50),ForeignKey("skills.skill_id", ondelete="CASCADE"),nullable=False,index=True)
    user_id = Column(String(50), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "skill_id",
            "user_id",
            name="uq_skill_holder",
        ),
    )


class URLRecord(Base):
    __tablename__ = "urls"

    url_id = Column(String(50), primary_key=True)
    url = Column(Text, unique=True, nullable=False)
    is_visited = Column(Boolean, nullable=False, default=False)

