from app.schemas.interactions import InteractionState
from app.services.analytics import AnalyticsService


class InteractionService:
    def __init__(self, repository, assets):
        self.repository = repository
        self.assets = assets

    async def state(self, user_id, asset_id):
        await self.assets.require_asset(asset_id)
        state = await self.repository.state(user_id, asset_id)
        return InteractionState.model_validate(state) if state else InteractionState()

    async def change(self, user_id, asset_id, action, active):
        await self.repository.lock_user(user_id)
        await self.assets.require_asset(asset_id)
        state = await self.repository.state(user_id, asset_id)
        if state is None:
            state = self.repository.add_state(user_id, asset_id)
        if action == "view":
            self.repository.event(user_id, asset_id, "VIEW")
            AnalyticsService(self.repository.session).record(
                "asset_viewed", user_id, asset_id=str(asset_id)
            )
        else:
            field, enable, disable = {
                "like": ("liked", "LIKE", "UNLIKE"),
                "dislike": ("disliked", "DISLIKE", "REMOVE_DISLIKE"),
                "save": ("saved", "SAVE", "UNSAVE"),
            }[action]
            if getattr(state, field) != active:
                if active and action in ("like", "dislike"):
                    other = "disliked" if action == "like" else "liked"
                    if getattr(state, other):
                        setattr(state, other, False)
                        self.repository.event(
                            user_id, asset_id, "REMOVE_DISLIKE" if other == "disliked" else "UNLIKE"
                        )
                setattr(state, field, active)
                self.repository.event(user_id, asset_id, enable if active else disable)
                event = {"like": "asset_liked", "dislike": "asset_disliked",
                         "save": "asset_saved" if active else "asset_unsaved"}[action]
                if active or action == "save":
                    AnalyticsService(self.repository.session).record(
                        event, user_id, asset_id=str(asset_id)
                    )
        await self.repository.commit()
        return InteractionState.model_validate(state)

    async def saved(self, user_id):
        return await self.assets.summary(await self.repository.saved(user_id))
