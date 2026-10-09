from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.learn import LearnRepository
from app.schemas.learn import ArticleEnvelope, ArticleListEnvelope
from app.services.learn import LearnService

router = APIRouter(prefix="/api/v1/learn/articles", tags=["Learn"])


def get_learn_service(session: AsyncSession = Depends(get_session)):
    return LearnService(LearnRepository(session))


@router.get("", response_model=ArticleListEnvelope)
async def articles(service=Depends(get_learn_service)):
    return {"data": await service.articles()}


@router.get("/{slug}", response_model=ArticleEnvelope)
async def article(
    slug: Annotated[str, Path(max_length=128, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")],
    service=Depends(get_learn_service),
):
    return {"data": await service.article(slug)}
