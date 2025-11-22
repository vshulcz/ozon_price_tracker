from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.db.db import get_session, init_engine_and_schema
from app.db.migrations import run_migrations
from app.db.models import User


@pytest.mark.asyncio
async def test_init_engine_and_schema_with_migrations_creates_tables(tmp_path: Path):
    db_file = tmp_path / "db_test.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    run_migrations(dsn)

    engine, _ = init_engine_and_schema(dsn)

    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name in ('users','products','price_history')"
            )
        )
        names = {row[0] for row in res.fetchall()}
    assert {"users", "products", "price_history"}.issubset(names)

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_session_inserts_and_reads_user(tmp_path: Path):
    db_file = tmp_path / "db_insert.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    run_migrations(dsn)

    engine, session_maker = init_engine_and_schema(dsn)

    async for s in get_session(session_maker):
        u = User(tg_user_id=123456789)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        assert u.id is not None
        break

    async with session_maker() as s2:
        count = await s2.scalar(select(func.count()).select_from(User))
        assert count == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_session_returns_distinct_sessions(tmp_path: Path):
    db_file = tmp_path / "db_sessions.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    run_migrations(dsn)

    engine, session_maker = init_engine_and_schema(dsn)

    first = None
    async for s in get_session(session_maker):
        first = s
        await s.execute(text("SELECT 1"))
        break

    second = None
    async for s in get_session(session_maker):
        second = s
        await s.execute(text("SELECT 1"))
        break

    assert first is not None and second is not None
    assert first is not second, "ожидали разные объекты сессий из разных вызовов get_session"

    await engine.dispose()
