"""Run inside the backend container against an isolated temporary PostgreSQL DB."""

import asyncio
import os
import subprocess
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def main():
    url = make_url(get_settings().database_url)
    name = "yudy_migration_test_" + uuid.uuid4().hex
    admin = create_async_engine(url, isolation_level="AUTOCOMMIT")
    created = False
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        env = dict(os.environ, DATABASE_URL=url.set(database=name).render_as_string(
            hide_password=False
        ))
        for command in (("upgrade", "head"), ("check",), ("downgrade", "0009"),
                        ("upgrade", "head"), ("check",)):
            subprocess.run(["alembic", *command], env=env, check=True)
        engine = create_async_engine(url.set(database=name))
        try:
            async with engine.connect() as connection:
                version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
                assert version == "0010"
                assert await connection.scalar(text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name='analytics_events' AND column_name='properties'"
                )) == "jsonb"
        finally:
            await engine.dispose()
        print("PASS: clean PostgreSQL migrations, 0010 downgrade/re-upgrade and JSONB schema")
    finally:
        if created:
            async with admin.connect() as connection:
                await connection.execute(text(f'DROP DATABASE "{name}"'))
        await admin.dispose()


if __name__ == "__main__":
    asyncio.run(main())
