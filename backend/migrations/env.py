import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.database import Base
from app.models import (
    analytics,  # noqa: F401
    assets,  # noqa: F401
    interactions,  # noqa: F401
    learn,  # noqa: F401
    profile,  # noqa: F401
    risk,  # noqa: F401
)
from app.models.auth import RefreshToken, User  # noqa: F401
from app.models.legal import LegalDocument, UserConsent  # noqa: F401

config = context.config
target_metadata = Base.metadata


def run(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def migrate():
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=get_settings().database_url, target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(migrate())
