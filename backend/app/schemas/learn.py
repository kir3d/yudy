from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArticleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    slug: str
    title: str
    summary: str
    updated_at: datetime


class ArticleDetail(ArticleSummary):
    content: str


class ArticleListEnvelope(BaseModel):
    data: list[ArticleSummary]


class ArticleEnvelope(BaseModel):
    data: ArticleDetail


class SeedArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=128)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    content: str = Field(min_length=1)
    sort_order: int = Field(ge=0)
    active: bool = True
