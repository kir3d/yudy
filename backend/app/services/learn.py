from fastapi import HTTPException

from app.schemas.learn import ArticleDetail, ArticleSummary
from app.services.analytics import AnalyticsService


class LearnService:
    def __init__(self, repository):
        self.repository = repository

    async def articles(self):
        return [
            ArticleSummary.model_validate(article) for article in await self.repository.articles()
        ]

    async def article(self, slug):
        article = await self.repository.article(slug)
        if article is None:
            raise HTTPException(404, "Article is unavailable")
        AnalyticsService(self.repository.session).record(
            "learn_article_opened", article_id=str(article.id), slug=article.slug
        )
        await self.repository.session.commit()
        return ArticleDetail.model_validate(article)
