import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.auth import utcnow


class AssetInteractionState(Base):
    __tablename__ = "asset_interaction_states"
    __table_args__ = (CheckConstraint("NOT (liked AND disliked)", name="ck_interaction_exclusive"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id"), primary_key=True)
    liked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disliked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AssetInteraction(Base):
    __tablename__ = "asset_interactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('LIKE','UNLIKE','DISLIKE','REMOVE_DISLIKE',"
            "'SAVE','UNSAVE','VIEW','BUY_CLICK')",
            name="ck_interaction_type",
        ),
        Index("ix_interactions_user_asset", "user_id", "asset_id"),
        Index("ix_interactions_user_type", "user_id", "type"),
        Index("ix_interactions_asset_type", "asset_id", "type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSON().with_variant(JSONB(), "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
