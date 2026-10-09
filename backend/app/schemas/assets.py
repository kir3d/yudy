from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.assets import AssetType


class HistoryPeriod(StrEnum):
    DAY = "1D"
    MONTH = "1M"
    YEAR = "1Y"
    THREE_YEARS = "3Y"
    ALL = "ALL"


class AssetSort(StrEnum):
    SYMBOL = "symbol"
    NAME = "name"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


class FundamentalsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    price: Decimal | None = None
    market_cap: Decimal | None = None
    pe: Decimal | None = None
    eps: Decimal | None = None
    revenue: Decimal | None = None
    revenue_growth: Decimal | None = None
    net_income: Decimal | None = None
    debt: Decimal | None = None
    cash_flow: Decimal | None = None
    dividend: Decimal | None = None
    dividend_yield: Decimal | None = None


class FundamentalsResponse(FundamentalsInput):
    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)
    updated_at: datetime


class AssetSummary(BaseModel):
    id: UUID
    symbol: str
    name: str
    asset_type: AssetType
    sector: str | None
    industry: str | None
    region: str | None
    market: str | None
    currency: str
    price: Decimal | None
    as_of: datetime | None
    performance_1y: Decimal | None
    has_tokenized_representation: bool


class PricePoint(BaseModel):
    timestamp: datetime
    close: Decimal


class PriceHistory(BaseModel):
    period: HistoryPeriod
    points: list[PricePoint]
    performance_percent: Decimal | None


class TokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    symbol: str
    token_name: str
    issuer: str | None
    tokenization_provider: str | None
    backing: str | None
    proof_of_reserves_url: str | None
    oracle_provider: str | None
    oracle_reference: str | None
    corporate_actions_info: str | None
    availability: str | None


class AssetRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    description: str


class FilterOption(BaseModel):
    code: str
    title: str


class AssetFilters(BaseModel):
    regions: list[FilterOption]
    markets: list[FilterOption]
    sectors: list[FilterOption]
    industries: list[FilterOption]
    themes: list[FilterOption]
    asset_types: list[FilterOption]


class AssetDetails(AssetSummary):
    description: str
    country: str | None
    themes: list[FilterOption]
    fundamentals: FundamentalsResponse | None
    tokens: list[TokenResponse]
    risks: list[AssetRiskResponse]
    history: PriceHistory


class DemoMeta(BaseModel):
    data_mode: str = "demo"


class CatalogMeta(DemoMeta):
    total: int
    next_cursor: str | None


class CatalogEnvelope(BaseModel):
    data: list[AssetSummary]
    meta: CatalogMeta


class DetailEnvelope(BaseModel):
    data: AssetDetails
    meta: DemoMeta = Field(default_factory=DemoMeta)


class HistoryEnvelope(BaseModel):
    data: PriceHistory
    meta: DemoMeta = Field(default_factory=DemoMeta)


class FiltersEnvelope(BaseModel):
    data: AssetFilters
    meta: DemoMeta = Field(default_factory=DemoMeta)
