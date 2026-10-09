from fastapi import Request
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def session_factory():
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is required for database operations")
    engine = create_async_engine(url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request):
    factory = request.app.state.session_factory
    if factory is None:
        raise RuntimeError("DATABASE_URL is required for database operations")
    async with factory() as session:
        yield session
