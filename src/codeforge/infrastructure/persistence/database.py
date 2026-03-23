from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command

from .models import Base

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parents[4]


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _sync_url(url: str) -> str:
    return url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")


def _run_migrations(database_url: str) -> bool:
    try:
        alembic_ini = _PROJECT_ROOT / "alembic.ini"
        if not alembic_ini.exists():
            return False

        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", _sync_url(database_url))
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")
        return True
    except Exception as exc:
        logger.warning("Alembic migration failed, falling back to create_all: %s", exc)
        return False


async def init_database(engine: AsyncEngine) -> None:
    db_url = engine.url.render_as_string(hide_password=False)
    is_sqlite = "sqlite" in db_url

    if is_sqlite:
        alembic_dir = _PROJECT_ROOT / "alembic"
        if alembic_dir.exists() and "codeforge.db" in db_url and _run_migrations(db_url):
            return
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    _run_migrations(db_url)
    logger.info("PostgreSQL database ready")


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
