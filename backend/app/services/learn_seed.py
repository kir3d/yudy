import json

from sqlalchemy import select

from app.models.learn import LearnArticle
from app.schemas.learn import SeedArticle


async def seed_articles(session, path):
    data = json.loads(path.read_text())
    articles = [SeedArticle.model_validate(a) for a in data["articles"]]
    slugs = [a.slug for a in articles]
    if not articles or len(set(slugs)) != len(slugs):
        raise ValueError("Learn manifest must contain unique article slugs")
    for article in articles:
        row = await session.scalar(select(LearnArticle).where(LearnArticle.slug == article.slug))
        if row is None:
            session.add(LearnArticle(**article.model_dump()))
        else:
            for name, value in article.model_dump().items():
                if getattr(row, name) != value:
                    setattr(row, name, value)
    await session.commit()
