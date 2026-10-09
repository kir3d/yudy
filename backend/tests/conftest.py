import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.auth import get_rate_limiter
from app.core.config import Settings, get_settings
from app.core.database import Base, get_session
from app.main import app
from app.services.legal_seed import seed_legal_documents
from app.services.risk_seed import seed_risk_questionnaire
from app.services.taxonomy_seed import seed_taxonomy


class TestLimiter:
    def __init__(self):
        self.count = 0

    async def check(self, identity):
        from fastapi import HTTPException

        self.count += 1
        if self.count > 20:
            raise HTTPException(429, "Too many authentication attempts")


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            await seed_legal_documents(session, Settings().legal_documents_path)
            await seed_taxonomy(session, Settings().taxonomy_path)
            await seed_risk_questionnaire(session, Settings().risk_questionnaire_path)

    asyncio.run(prepare())

    async def session_override():
        async with factory() as session:
            yield session

    settings = Settings(jwt_secret="test-key-only-" + "x" * 32, database_url="", redis_url="")
    monkeypatch.setattr("app.main.settings", settings)
    limiter = TestLimiter()
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        with TestClient(app) as client:
            client.db_factory = factory
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
