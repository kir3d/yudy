from sqlalchemy import delete, select

from app.models.auth import User
from app.models.profile import UserProfile


class ProfileRepository:
    def __init__(self, session):
        self.session = session

    async def taxonomy(self, model):
        return list(
            (
                await self.session.scalars(
                    select(model).where(model.active.is_(True)).order_by(model.title)
                )
            ).all()
        )

    async def lock_user(self, user_id):
        await self.session.scalar(select(User).where(User.id == user_id).with_for_update())

    async def profile(self, user_id):
        return await self.session.get(UserProfile, user_id)

    async def selections(self, model, column, user_id):
        return list(
            (
                await self.session.scalars(
                    select(column).where(model.user_id == user_id).order_by(column)
                )
            ).all()
        )

    async def replace(self, model, column, user_id, values):
        await self.session.execute(delete(model).where(model.user_id == user_id))
        self.session.add_all(model(user_id=user_id, **{column.key: value}) for value in values)
