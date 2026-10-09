from datetime import timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.schemas.assets import FundamentalsResponse, HistoryPeriod, PriceHistory, PricePoint


class MarketDataProvider(Protocol):
    async def quotes(self, asset_ids: list[UUID]) -> dict: ...
    async def history(self, asset_id: UUID, period: HistoryPeriod) -> PriceHistory: ...
    async def fundamentals(self, asset_id: UUID) -> FundamentalsResponse | None: ...


def performance(points):
    if len(points) < 2 or points[0].close == 0:
        return None
    return ((points[-1].close / points[0].close - 1) * 100).quantize(Decimal("0.01"))


def period_points(points, period):
    if not points or period == HistoryPeriod.ALL:
        return points
    days = {
        HistoryPeriod.DAY: 1,
        HistoryPeriod.MONTH: 30,
        HistoryPeriod.YEAR: 365,
        HistoryPeriod.THREE_YEARS: 1095,
    }
    cutoff = points[-1].timestamp - timedelta(days=days[period])
    return [point for point in points if point.timestamp >= cutoff]


class DemoMarketDataProvider:
    def __init__(self, repository):
        self.repository = repository

    async def quotes(self, asset_ids):
        histories = {asset_id: [] for asset_id in asset_ids}
        for point in await self.repository.history(asset_ids):
            histories[point.asset_id].append(point)
        return {
            asset_id: {
                "price": points[-1].close if points else None,
                "as_of": points[-1].timestamp if points else None,
                "performance_1y": performance(period_points(points, HistoryPeriod.YEAR)),
            }
            for asset_id, points in histories.items()
        }

    async def history(self, asset_id, period):
        points = period_points(await self.repository.history([asset_id]), period)
        return PriceHistory(
            period=period,
            points=[PricePoint(timestamp=point.timestamp, close=point.close) for point in points],
            performance_percent=performance(points),
        )

    async def fundamentals(self, asset_id):
        row = await self.repository.fundamentals(asset_id)
        return FundamentalsResponse.model_validate(row) if row is not None else None
