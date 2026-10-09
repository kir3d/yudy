import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.auth import utcnow


class Experience(StrEnum):
    NEW = "NEW"
    SOME = "SOME"
    REGULAR = "REGULAR"
    EXPERIENCED = "EXPERIENCED"


class Horizon(StrEnum):
    UNDER_ONE = "UNDER_ONE"
    ONE_THREE = "ONE_THREE"
    THREE_FIVE = "THREE_FIVE"
    FIVE_PLUS = "FIVE_PLUS"


class InterestKind(StrEnum):
    SECTOR = "SECTOR"
    THEME = "THEME"


class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    experience: Mapped[Experience] = mapped_column(
        Enum(Experience, native_enum=False, create_constraint=True, name="experience")
    )
    investment_horizon: Mapped[Horizon] = mapped_column(
        Enum(Horizon, native_enum=False, create_constraint=True, name="horizon")
    )
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Taxonomy:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Goal(Taxonomy, Base):
    __tablename__ = "goals"


class Interest(Taxonomy, Base):
    __tablename__ = "interests"
    kind: Mapped[InterestKind] = mapped_column(
        Enum(InterestKind, native_enum=False, create_constraint=True, name="interest_kind")
    )


class Region(Taxonomy, Base):
    __tablename__ = "regions"


class UserGoal(Base):
    __tablename__ = "user_goals"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    goal_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("goals.id"), primary_key=True)


class UserInterest(Base):
    __tablename__ = "user_interests"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    interest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("interests.id"), primary_key=True
    )


class UserExcludedInterest(Base):
    __tablename__ = "user_excluded_interests"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    interest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("interests.id"), primary_key=True
    )


class UserRegion(Base):
    __tablename__ = "user_regions"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    region_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("regions.id"), primary_key=True)
