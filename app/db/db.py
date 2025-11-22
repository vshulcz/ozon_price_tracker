from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

async_engine: AsyncEngine | None = None
async_session: async_sessionmaker[AsyncSession] | None = None


def init_engine_and_schema(dsn: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    async_engine = create_async_engine(
        dsn,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)
    return async_engine, async_session


async def get_session(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_maker() as session:
        yield session
