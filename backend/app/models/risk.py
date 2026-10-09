import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.auth import utcnow


class RiskCategory(StrEnum):
    CONSERVATIVE = "Conservative"
    BALANCED = "Balanced"
    GROWTH = "Growth"


class RiskQuestionnaire(Base):
    __tablename__ = "risk_questionnaires"
    __table_args__ = (
        CheckConstraint(
            "conservative_max >= 0 AND conservative_max < balanced_max AND balanced_max < 100",
            name="ck_risk_thresholds",
        ),
        Index(
            "uq_risk_active",
            "active",
            unique=True,
            postgresql_where=text("active = true"),
            sqlite_where=text("active = 1"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(64), unique=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    conservative_max: Mapped[int] = mapped_column(Integer)
    balanced_max: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RiskQuestion(Base):
    __tablename__ = "risk_questions"
    __table_args__ = (UniqueConstraint("questionnaire_id", "code", name="uq_risk_question_code"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    questionnaire_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("risk_questionnaires.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RiskAnswerOption(Base):
    __tablename__ = "risk_answer_options"
    __table_args__ = (
        UniqueConstraint("question_id", "code", name="uq_risk_option_code"),
        CheckConstraint("score >= 0", name="ck_risk_option_score"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("risk_questions.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer)


class RiskProfile(Base):
    __tablename__ = "risk_profiles"
    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_risk_profile_score"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_category: Mapped[RiskCategory] = mapped_column(
        Enum(RiskCategory, native_enum=False, create_constraint=True, name="risk_category")
    )
    questionnaire_version: Mapped[str] = mapped_column(
        String(64), ForeignKey("risk_questionnaires.version")
    )
    answers: Mapped[list[dict]] = mapped_column(JSON)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
