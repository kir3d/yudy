from fastapi import HTTPException

from app.services.analytics import AnalyticsService


class BuyService:
    def __init__(self, repository, assets, provider):
        self.repository = repository
        self.assets = assets
        self.provider = provider

    async def link(self, asset_id, token_id):
        await self.assets.require_asset(asset_id)
        token = next(
            (t for t in await self.assets.repository.tokens(asset_id) if t.id == token_id), None
        )
        if token is None:
            raise HTTPException(404, "Tokenized representation is unavailable for this asset")
        return await self.provider.get_buy_link(token)

    async def confirm(self, user_id, asset_id, body):
        await self.repository.lock_user(user_id)
        link = await self.link(asset_id, body.tokenized_asset_id)
        existing = await self.repository.click(body.event_id)
        if existing is not None:
            if (
                existing.user_id != user_id
                or existing.asset_id != asset_id
                or existing.type != "BUY_CLICK"
                or (existing.metadata_json or {}).get("tokenized_asset_id")
                != str(body.tokenized_asset_id)
            ):
                raise HTTPException(409, "Confirmation ID has already been used")
        else:
            await self.repository.record(
                body.event_id,
                user_id,
                asset_id,
                {
                    "tokenized_asset_id": str(body.tokenized_asset_id),
                    "provider": link.provider,
                    "demo": True,
                },
            )
            AnalyticsService(self.repository.session).record(
                "buy_clicked", user_id, asset_id=str(asset_id),
                tokenized_asset_id=str(body.tokenized_asset_id),
                interaction_id=str(body.event_id), provider=link.provider, demo=True,
            )
            await self.repository.commit()
        return link
