from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import RefreshToken, User


class AuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def user_by_email(self, email):
        return await self.session.scalar(select(User).where(User.email == email))

    async def user_by_id(self, user_id):
        return await self.session.get(User, user_id)

    async def refresh_by_hash(self, hashed):
        return await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hashed).with_for_update()
        )

    async def session_by_id(self, session_id):
        return await self.session.get(RefreshToken, session_id)

    async def add(self, record):
        self.session.add(record)
        await self.session.flush()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
