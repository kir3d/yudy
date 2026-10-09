import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.buy import router as buy_router
from app.api.health import router
from app.api.interactions import router as interactions_router
from app.api.learn import router as learn_router
from app.api.legal import router as legal_router
from app.api.profile import router as profile_router
from app.api.risk import router as risk_router
from app.api.selection import router as selection_router
from app.core.config import get_settings
from app.core.database import session_factory
from app.core.errors import install_error_handlers
from app.core.http import install_http_middleware
from app.services.asset_seed import seed_assets
from app.services.learn_seed import seed_articles
from app.services.legal_seed import seed_legal_documents
from app.services.risk_seed import seed_risk_questionnaire
from app.services.taxonomy_seed import seed_taxonomy

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url and len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    engine, factory = session_factory() if settings.database_url else (None, None)
    app.state.session_factory = factory
    app.state.redis = Redis.from_url(settings.redis_url) if settings.redis_url else None
    try:
        if factory is not None:
            async with factory() as session:
                await seed_legal_documents(session, settings.legal_documents_path)
                await seed_taxonomy(session, settings.taxonomy_path)
                await seed_risk_questionnaire(session, settings.risk_questionnaire_path)
                await seed_assets(session, settings.demo_market_path)
                await seed_articles(session, settings.learn_articles_path)
        yield
    finally:
        if engine is not None:
            await engine.dispose()
        if app.state.redis is not None:
            await app.state.redis.aclose()


app = FastAPI(title="YUDY API", version="0.1.0", debug=False, lifespan=lifespan)
install_error_handlers(app)
install_http_middleware(app, settings)
app.include_router(router)
app.include_router(auth_router)
app.include_router(legal_router)

app.include_router(profile_router)

app.include_router(risk_router)

app.include_router(assets_router)

app.include_router(buy_router)

app.include_router(interactions_router)

app.include_router(selection_router)

app.include_router(learn_router)
