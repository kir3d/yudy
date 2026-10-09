from sqlalchemy import select

from app.models.learn import LearnArticle


class LearnRepository:
    def __init__(self, session):
        self.session = session

    async def articles(self):
        return list(
            await self.session.scalars(
                select(LearnArticle)
                .where(LearnArticle.active.is_(True))
                .order_by(LearnArticle.sort_order, LearnArticle.slug)
            )
        )

    async def article(self, slug):
        return await self.session.scalar(
            select(LearnArticle).where(LearnArticle.slug == slug, LearnArticle.active.is_(True))
        )
