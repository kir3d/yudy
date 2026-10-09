import base64
import hashlib
import hmac
import json

from fastapi import HTTPException

from app.schemas.assets import (
    AssetDetails,
    AssetFilters,
    AssetRiskResponse,
    AssetSummary,
    CatalogEnvelope,
    CatalogMeta,
    FilterOption,
    HistoryPeriod,
    TokenResponse,
)


class AssetService:
    def __init__(self, repository, provider, cursor_secret):
        self.repository = repository
        self.provider = provider
        self.cursor_secret = cursor_secret.encode()

    def cursor(self, offset, fingerprint):
        body = json.dumps({"offset": offset, "query": fingerprint}, separators=(",", ":")).encode()
        signature = hmac.new(self.cursor_secret, body, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(body + signature).decode().rstrip("=")

    def offset(self, cursor, fingerprint):
        if cursor is None:
            return 0
        try:
            decoded = base64.b64decode(
                cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
            )
            body, signature = decoded[:-32], decoded[-32:]
            if not hmac.compare_digest(
                signature, hmac.new(self.cursor_secret, body, hashlib.sha256).digest()
            ):
                raise ValueError()
            payload = json.loads(body)
            if (
                payload["query"] != fingerprint
                or type(payload["offset"]) is not int
                or not 0 <= payload["offset"] <= 1000000
            ):
                raise ValueError()
            return payload["offset"]
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise HTTPException(400, "Invalid cursor for this catalog query") from None

    async def summary(self, assets):
        ids = [asset.id for asset in assets]
        quotes = await self.provider.quotes(ids)
        tokens = await self.repository.tokenized_ids(ids)
        return [
            AssetSummary(
                id=asset.id,
                symbol=asset.symbol,
                name=asset.name,
                asset_type=asset.asset_type,
                sector=asset.sector,
                industry=asset.industry,
                region=asset.region,
                market=asset.market,
                currency=asset.currency,
                has_tokenized_representation=asset.id in tokens,
                **quotes[asset.id],
            )
            for asset in assets
        ]

    async def catalog(self, filters, sort, limit, cursor):
        normalized = {
            key: value.strip().casefold() if value else None for key, value in filters.items()
        }
        fingerprint = hashlib.sha256(
            json.dumps({**normalized, "sort": sort}, sort_keys=True).encode()
        ).hexdigest()
        offset = self.offset(cursor, fingerprint)
        assets, total = await self.repository.catalog(normalized, sort, offset, limit)
        next_cursor = (
            self.cursor(offset + len(assets), fingerprint) if offset + len(assets) < total else None
        )
        return CatalogEnvelope(
            data=await self.summary(assets), meta=CatalogMeta(total=total, next_cursor=next_cursor)
        )

    async def require_asset(self, asset_id):
        asset = await self.repository.asset(asset_id)
        if asset is None:
            raise HTTPException(404, "Asset is unavailable")
        return asset

    async def details(self, asset_id):
        asset = await self.require_asset(asset_id)
        summary = (await self.summary([asset]))[0]
        return AssetDetails(
            **summary.model_dump(),
            description=asset.description,
            country=asset.country,
            themes=[
                FilterOption(code=theme.code, title=theme.title)
                for theme in await self.repository.themes(asset.id)
            ],
            fundamentals=await self.provider.fundamentals(asset.id),
            tokens=[
                TokenResponse.model_validate(token)
                for token in await self.repository.tokens(asset.id)
            ],
            risks=[
                AssetRiskResponse.model_validate(risk)
                for risk in await self.repository.risks(asset.id)
            ],
            history=await self.provider.history(asset.id, HistoryPeriod.YEAR),
        )

    async def history(self, asset_id, period):
        await self.require_asset(asset_id)
        return await self.provider.history(asset_id, period)

    async def filters(self):
        facets = await self.repository.facets()

        def options(key):
            return [
                FilterOption(
                    code=str(value),
                    title=(
                        facets["region_titles"].get(value, value)
                        if key == "region"
                        else str(value).replace("_", " ").title()
                    ),
                )
                for value in facets[key]
            ]

        return AssetFilters(
            regions=options("region"),
            markets=options("market"),
            sectors=options("sector"),
            industries=options("industry"),
            asset_types=options("asset_type"),
            themes=[
                FilterOption(code=theme.code, title=theme.title)
                for theme in await self.repository.themes()
            ],
        )
