from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.legal import LegalDocument, UserConsent


class LegalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def active_documents(self, lock=False):
        query = (
            select(LegalDocument).where(LegalDocument.active.is_(True)).order_by(LegalDocument.type)
        )
        if lock:
            query = query.with_for_update(read=True)
        return list((await self.session.scalars(query)).all())

    async def user_consents(self, user_id):
        return list(
            (
                await self.session.scalars(
                    select(UserConsent).where(UserConsent.user_id == user_id)
                )
            ).all()
        )

    async def lock_user(self, user_id):
        await self.session.scalar(select(User).where(User.id == user_id).with_for_update())

    async def add_consents(self, consents):
        self.session.add_all(consents)
        await self.session.flush()

    async def commit(self):
        await self.session.commit()
