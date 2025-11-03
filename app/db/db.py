from __future__ import annotations
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from app.db.models import Base

async_engine: AsyncEngine | None = None
async_session: async_sessionmaker[AsyncSession] | None = None


async def init_engine_and_schema(
    dsn: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global async_engine, async_session
    async_engine = create_async_engine(dsn, pool_size=10, max_overflow=20)
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return async_engine, async_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    assert async_session is not None
    async with async_session() as session:
        yield session
