from sqlalchemy import func, or_, select

from app.models.assets import (
    Asset,
    AssetFundamentals,
    AssetPrice,
    AssetRisk,
    AssetTheme,
    TokenizedAsset,
)
from app.models.profile import Interest, InterestKind, Region
from app.schemas.assets import AssetSort


class AssetRepository:
    def __init__(self, session):
        self.session = session

    def query(self, filters):
        query = select(Asset).where(Asset.active.is_(True))
        for key in ("region", "market", "sector", "industry", "asset_type"):
            value = filters.get(key)
            if value:
                query = query.where(func.lower(getattr(Asset, key)) == value)
        if filters.get("search"):
            query = query.where(
                or_(
                    func.lower(Asset.symbol).contains(filters["search"], autoescape=True),
                    func.lower(Asset.name).contains(filters["search"], autoescape=True),
                )
            )
        if filters.get("theme"):
            query = query.where(
                Asset.id.in_(
                    select(AssetTheme.asset_id)
                    .join(Interest, Interest.id == AssetTheme.interest_id)
                    .where(
                        Interest.code == filters["theme"],
                        Interest.active.is_(True),
                        Interest.kind == InterestKind.THEME,
                    )
                )
            )
        return query

    async def catalog(self, filters, sort, offset, limit):
        query = self.query(filters)
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        if sort in (AssetSort.PRICE_ASC, AssetSort.PRICE_DESC):
            price = (
                select(AssetPrice.close)
                .where(AssetPrice.asset_id == Asset.id)
                .order_by(AssetPrice.timestamp.desc())
                .limit(1)
                .scalar_subquery()
            )
            query = query.order_by(
                (price.asc() if sort == AssetSort.PRICE_ASC else price.desc()).nulls_last(),
                Asset.symbol,
                Asset.id,
            )
        else:
            query = query.order_by(Asset.name if sort == AssetSort.NAME else Asset.symbol, Asset.id)
        return list((await self.session.scalars(query.offset(offset).limit(limit))).all()), total

    async def asset(self, asset_id):
        return await self.session.scalar(
            select(Asset).where(Asset.id == asset_id, Asset.active.is_(True))
        )

    async def tokenized_ids(self, asset_ids):
        return set(
            (
                await self.session.scalars(
                    select(TokenizedAsset.asset_id).where(
                        TokenizedAsset.asset_id.in_(asset_ids), TokenizedAsset.active.is_(True)
                    )
                )
            ).all()
        )

    async def tokens(self, asset_id):
        return list(
            (
                await self.session.scalars(
                    select(TokenizedAsset)
                    .where(TokenizedAsset.asset_id == asset_id, TokenizedAsset.active.is_(True))
                    .order_by(TokenizedAsset.symbol)
                )
            ).all()
        )

    async def risks(self, asset_id):
        return list(
            (
                await self.session.scalars(
                    select(AssetRisk)
                    .where(AssetRisk.asset_id == asset_id, AssetRisk.active.is_(True))
                    .order_by(AssetRisk.sort_order, AssetRisk.id)
                )
            ).all()
        )

    async def themes(self, asset_id=None):
        query = (
            select(Interest)
            .join(AssetTheme, AssetTheme.interest_id == Interest.id)
            .join(Asset, Asset.id == AssetTheme.asset_id)
            .where(
                Asset.active.is_(True),
                Interest.active.is_(True),
                Interest.kind == InterestKind.THEME,
            )
        )
        if asset_id is not None:
            query = query.where(Asset.id == asset_id)
        return list((await self.session.scalars(query.distinct().order_by(Interest.title))).all())

    async def facets(self):
        result = {}
        for key in ("region", "market", "sector", "industry", "asset_type"):
            column = getattr(Asset, key)
            result[key] = list(
                (
                    await self.session.scalars(
                        select(column)
                        .where(Asset.active.is_(True), column.is_not(None))
                        .distinct()
                        .order_by(column)
                    )
                ).all()
            )
        result["region_titles"] = {
            row.code: row.title for row in (await self.session.scalars(select(Region))).all()
        }
        return result


class MarketRepository:
    def __init__(self, session):
        self.session = session

    async def history(self, asset_ids):
        return list(
            (
                await self.session.scalars(
                    select(AssetPrice)
                    .where(AssetPrice.asset_id.in_(asset_ids))
                    .order_by(AssetPrice.timestamp)
                )
            ).all()
        )

    async def fundamentals(self, asset_id):
        return await self.session.get(AssetFundamentals, asset_id)
