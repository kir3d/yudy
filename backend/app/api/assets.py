from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.integrations.market_data import DemoMarketDataProvider
from app.repositories.assets import AssetRepository, MarketRepository
from app.schemas.assets import (
    AssetSort,
    CatalogEnvelope,
    DetailEnvelope,
    FiltersEnvelope,
    HistoryEnvelope,
    HistoryPeriod,
)
from app.services.assets import AssetService

router = APIRouter(prefix="/api/v1/assets", tags=["Assets"])


def get_asset_service(session: AsyncSession = Depends(get_session), settings=Depends(get_settings)):
    return AssetService(
        AssetRepository(session),
        DemoMarketDataProvider(MarketRepository(session)),
        settings.jwt_secret,
    )


Filter = Annotated[str | None, Query(max_length=128)]


@router.get("", response_model=CatalogEnvelope)
async def catalog(
    search: Annotated[str | None, Query(max_length=100)] = None,
    region: Filter = None,
    market: Filter = None,
    sector: Filter = None,
    industry: Filter = None,
    theme: Filter = None,
    asset_type: Annotated[str | None, Query(pattern="(?i)^(stock|etf)$")] = None,
    sort: AssetSort = AssetSort.SYMBOL,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    service=Depends(get_asset_service),
):
    return await service.catalog(
        {
            "search": search,
            "region": region,
            "market": market,
            "sector": sector,
            "industry": industry,
            "theme": theme,
            "asset_type": asset_type,
        },
        sort,
        limit,
        cursor,
    )


@router.get("/filters", response_model=FiltersEnvelope)
async def filters(service=Depends(get_asset_service)):
    return FiltersEnvelope(data=await service.filters())


@router.get("/{asset_id}", response_model=DetailEnvelope)
async def details(asset_id: UUID, service=Depends(get_asset_service)):
    return DetailEnvelope(data=await service.details(asset_id))


@router.get("/{asset_id}/history", response_model=HistoryEnvelope)
async def history(
    asset_id: UUID, period: HistoryPeriod = HistoryPeriod.YEAR, service=Depends(get_asset_service)
):
    return HistoryEnvelope(data=await service.history(asset_id, period))
