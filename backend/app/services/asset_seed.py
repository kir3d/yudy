from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select

from app.models.assets import (
    Asset,
    AssetFundamentals,
    AssetPrice,
    AssetRisk,
    AssetTheme,
    AssetType,
    TokenizedAsset,
)
from app.models.profile import Interest, InterestKind
from app.schemas.assets import FundamentalsInput


class PriceSeed(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_bar(self):
        if self.timestamp.tzinfo is None:
            raise ValueError("Price timestamps must include a timezone")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("Invalid OHLC price range")
        return self


class TokenSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=64)
    token_name: str = Field(min_length=1, max_length=255)
    issuer: str | None = None
    tokenization_provider: str | None = None
    backing: str | None = None
    proof_of_reserves_url: str | None = None
    oracle_provider: str | None = None
    oracle_reference: str | None = None
    corporate_actions_info: str | None = None
    availability: str | None = None
    external_provider_id: str | None = None
    external_buy_url: str | None = None
    active: bool = True


class RiskSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    sort_order: int = Field(ge=0)


class AssetSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    asset_type: AssetType
    description: str = Field(min_length=1)
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    region: str | None = None
    market: str | None = None
    currency: str = Field(min_length=1, max_length=8)
    active: bool = True
    theme_codes: list[str] = Field(default_factory=list)
    fundamentals: FundamentalsInput
    prices: list[PriceSeed] = Field(min_length=1, max_length=10000)
    tokens: list[TokenSeed] = Field(default_factory=list)
    risks: list[RiskSeed] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_data(self):
        for values in (
            [item.timestamp for item in self.prices],
            [item.symbol for item in self.tokens],
            self.theme_codes,
            [risk.title for risk in self.risks],
        ):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate prices, tokens or themes")
        return self


class MarketSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_version: str = Field(min_length=1, max_length=64)
    assets: list[AssetSeed] = Field(min_length=30, max_length=50)

    @model_validator(mode="after")
    def unique_assets(self):
        if len({item.symbol for item in self.assets}) != len(self.assets):
            raise ValueError("Asset symbols must be unique")
        return self


async def seed_assets(session, path):
    manifest = MarketSeed.model_validate_json(path.read_text())
    themes = {
        row.code: row
        for row in (
            await session.scalars(
                select(Interest).where(
                    Interest.kind == InterestKind.THEME, Interest.active.is_(True)
                )
            )
        ).all()
    }
    if any(code not in themes for item in manifest.assets for code in item.theme_codes):
        raise ValueError("Asset themes must refer to active theme-type interests")
    for item in manifest.assets:
        asset = await session.scalar(select(Asset).where(Asset.symbol == item.symbol))
        fields = item.model_dump(
            exclude={"fundamentals", "prices", "tokens", "risks", "theme_codes"}
        )
        if asset is None:
            asset = Asset(**fields)
            session.add(asset)
            await session.flush()
        else:
            for key, value in fields.items():
                setattr(asset, key, value)
        fundamentals = await session.get(AssetFundamentals, asset.id)
        if fundamentals is None:
            fundamentals = AssetFundamentals(asset_id=asset.id)
            session.add(fundamentals)
        for key, value in item.fundamentals.model_dump().items():
            setattr(fundamentals, key, value)
        fundamentals.updated_at = max(price.timestamp for price in item.prices)
        await session.execute(delete(AssetPrice).where(AssetPrice.asset_id == asset.id))
        session.add_all(
            AssetPrice(asset_id=asset.id, **price.model_dump()) for price in item.prices
        )
        await session.execute(delete(AssetTheme).where(AssetTheme.asset_id == asset.id))
        session.add_all(
            AssetTheme(asset_id=asset.id, interest_id=themes[code].id) for code in item.theme_codes
        )
        existing_tokens = {
            token.symbol: token
            for token in (
                await session.scalars(
                    select(TokenizedAsset).where(TokenizedAsset.asset_id == asset.id)
                )
            ).all()
        }
        for token in existing_tokens.values():
            token.active = False
        for token in item.tokens:
            row = existing_tokens.get(token.symbol)
            if row is None:
                row = TokenizedAsset(asset_id=asset.id)
                session.add(row)
            for key, value in token.model_dump().items():
                setattr(row, key, value)
        existing_risks = {
            risk.title: risk
            for risk in (
                await session.scalars(select(AssetRisk).where(AssetRisk.asset_id == asset.id))
            ).all()
        }
        for risk in existing_risks.values():
            risk.active = False
        for risk in item.risks:
            row = existing_risks.get(risk.title)
            if row is None:
                row = AssetRisk(asset_id=asset.id)
                session.add(row)
            for key, value in risk.model_dump().items():
                setattr(row, key, value)
            row.active = True
    await session.commit()
