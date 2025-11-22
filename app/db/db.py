from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

async_engine: AsyncEngine | None = None
async_session: async_sessionmaker[AsyncSession] | None = None


def init_engine_and_schema(dsn: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    safe_dsn = dsn.split("@")[-1] if "@" in dsn else dsn
    logger.info("🗄️  Initializing database connection | DSN: %s", safe_dsn)

    try:
        async_engine = create_async_engine(
            dsn,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        async_session = async_sessionmaker(async_engine, expire_on_commit=False)
        logger.info("Database engine initialized | Pool size: 10 | Max overflow: 20")
        return async_engine, async_session
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        raise


async def get_session(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_maker() as session:
        yield session
