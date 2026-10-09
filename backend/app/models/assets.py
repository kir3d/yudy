import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.auth import utcnow


class AssetType(StrEnum):
    STOCK = "STOCK"
    ETF = "ETF"


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, native_enum=False, create_constraint=True, name="asset_type"), index=True
    )
    description: Mapped[str] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(String(128), index=True)
    industry: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(64), index=True)
    market: Mapped[str | None] = mapped_column(String(128))
    logo_url: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(8))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AssetTheme(Base):
    __tablename__ = "asset_themes"
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id"), primary_key=True)
    interest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("interests.id"), primary_key=True
    )


class AssetFundamentals(Base):
    __tablename__ = "asset_fundamentals"
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id"), primary_key=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    pe: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    eps: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    revenue_growth: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    debt: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    dividend: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssetPrice(Base):
    __tablename__ = "asset_prices"
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id"), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))


class TokenizedAsset(Base):
    __tablename__ = "tokenized_assets"
    __table_args__ = (UniqueConstraint("asset_id", "symbol", name="uq_asset_token_symbol"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(64))
    token_name: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str | None] = mapped_column(String(255))
    tokenization_provider: Mapped[str | None] = mapped_column(String(255))
    backing: Mapped[str | None] = mapped_column(Text)
    proof_of_reserves_url: Mapped[str | None] = mapped_column(Text)
    oracle_provider: Mapped[str | None] = mapped_column(String(255))
    oracle_reference: Mapped[str | None] = mapped_column(Text)
    corporate_actions_info: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str | None] = mapped_column(String(255))
    external_provider_id: Mapped[str | None] = mapped_column(String(64))
    external_buy_url: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AssetRisk(Base):
    __tablename__ = "asset_risks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
