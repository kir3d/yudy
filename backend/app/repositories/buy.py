from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.interactions import AssetInteraction
from app.repositories.interactions import InteractionRepository


class BuyRepository(InteractionRepository):
    async def click(self, event_id):
        return await self.session.get(AssetInteraction, event_id)

    async def record(self, event_id, user_id, asset_id, metadata):
        self.session.add(
            AssetInteraction(
                id=event_id,
                user_id=user_id,
                asset_id=asset_id,
                type="BUY_CLICK",
                metadata_json=metadata,
            )
        )

    async def commit(self):
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(409, "Confirmation ID has already been used") from None
