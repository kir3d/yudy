from sqlalchemy import select

from app.models.assets import Asset
from app.models.auth import User
from app.models.interactions import AssetInteraction, AssetInteractionState


class InteractionRepository:
    def __init__(self, session):
        self.session = session

    async def lock_user(self, user_id):
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())

    async def state(self, user_id, asset_id):
        return await self.session.get(AssetInteractionState, (user_id, asset_id))

    def add_state(self, user_id, asset_id):
        state = AssetInteractionState(
            user_id=user_id, asset_id=asset_id, liked=False, disliked=False, saved=False
        )
        self.session.add(state)
        return state

    def event(self, user_id, asset_id, kind):
        self.session.add(AssetInteraction(user_id=user_id, asset_id=asset_id, type=kind))

    async def commit(self):
        await self.session.commit()

    async def saved(self, user_id):
        return list(
            await self.session.scalars(
                select(Asset)
                .join(AssetInteractionState, Asset.id == AssetInteractionState.asset_id)
                .where(
                    AssetInteractionState.user_id == user_id,
                    AssetInteractionState.saved.is_(True),
                    Asset.active.is_(True),
                )
                .order_by(Asset.symbol, Asset.id)
            )
        )
