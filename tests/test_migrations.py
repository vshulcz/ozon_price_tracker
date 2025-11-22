from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.db import init_engine_and_schema
from app.db.migrations import (
    check_migrations_needed,
    get_current_revision,
    run_migrations,
)


@pytest.mark.asyncio
async def test_run_migrations_creates_tables(tmp_path: Path) -> None:
    db_file = tmp_path / "migration_test.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    run_migrations(dsn)

    engine, _ = init_engine_and_schema(dsn)

    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name IN ('users','products','price_history')"
            )
        )
        names = {row[0] for row in res.fetchall()}

    assert {"users", "products", "price_history"}.issubset(names)

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_migrations_creates_alembic_version_table(tmp_path: Path) -> None:
    db_file = tmp_path / "version_test.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    run_migrations(dsn)

    engine, _ = init_engine_and_schema(dsn)

    async with engine.begin() as conn:
        res = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        )
        table_exists = res.fetchone() is not None

    assert table_exists, "alembic_version table should be created"

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_current_revision_returns_none_for_empty_db(tmp_path: Path) -> None:
    db_file = tmp_path / "empty_db.sqlite3"
    dsn = f"sqlite:///{db_file}"

    engine, _ = init_engine_and_schema(f"sqlite+aiosqlite:///{db_file}")
    await engine.dispose()

    revision = get_current_revision(dsn)
    assert revision is None


def test_get_current_revision_returns_head_after_migrations(tmp_path: Path) -> None:
    db_file = tmp_path / "migrated_db.sqlite3"
    async_dsn = f"sqlite+aiosqlite:///{db_file}"
    sync_dsn = f"sqlite:///{db_file}"

    run_migrations(async_dsn)

    revision = get_current_revision(sync_dsn)

    assert revision is not None, "Revision should exist after migrations"
    assert len(revision) > 0, "Revision ID should not be empty"


@pytest.mark.asyncio
async def test_check_migrations_needed_returns_true_for_empty_db(tmp_path: Path) -> None:
    db_file = tmp_path / "check_empty.sqlite3"
    dsn = f"sqlite:///{db_file}"

    engine, _ = init_engine_and_schema(f"sqlite+aiosqlite:///{db_file}")
    await engine.dispose()

    needs_migration = check_migrations_needed(dsn)
    assert needs_migration is True


def test_check_migrations_needed_returns_false_after_migrations(tmp_path: Path) -> None:
    db_file = tmp_path / "check_migrated.sqlite3"
    async_dsn = f"sqlite+aiosqlite:///{db_file}"
    sync_dsn = f"sqlite:///{db_file}"

    run_migrations(async_dsn)

    needs_migration = check_migrations_needed(sync_dsn)
    assert needs_migration is False


@pytest.mark.asyncio
async def test_migrations_are_idempotent(tmp_path: Path) -> None:
    db_file = tmp_path / "idempotent_test.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    run_migrations(dsn)

    run_migrations(dsn)

    engine, _ = init_engine_and_schema(dsn)

    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name IN ('users','products','price_history')"
            )
        )
        names = {row[0] for row in res.fetchall()}

    assert {"users", "products", "price_history"}.issubset(names)

    await engine.dispose()


@pytest.mark.asyncio
async def test_init_engine_without_create_all(tmp_path: Path) -> None:
    db_file = tmp_path / "no_create_all.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    engine, _ = init_engine_and_schema(dsn)

    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name IN ('users','products','price_history')"
            )
        )
        names = {row[0] for row in res.fetchall()}

    assert len(names) == 0, "Tables should NOT be created without migrations"

    await engine.dispose()


@pytest.mark.asyncio
async def test_migrations_with_existing_data(tmp_path: Path) -> None:
    from app.db.models import User

    db_file = tmp_path / "existing_data.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    run_migrations(dsn)

    engine, session_maker = init_engine_and_schema(dsn)
    async with session_maker() as session:
        user = User(tg_user_id=123456789, language="ru")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    run_migrations(dsn)

    async with session_maker() as session:
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.tg_user_id == 123456789

    await engine.dispose()


def test_get_alembic_config_with_dsn(tmp_path: Path) -> None:
    from app.db.migrations import get_alembic_config

    dsn = "sqlite:///test.db"
    config = get_alembic_config(dsn)

    assert config.get_main_option("sqlalchemy.url") == dsn


def test_get_alembic_config_with_env_var(tmp_path: Path, monkeypatch) -> None:
    from app.db.migrations import get_alembic_config

    dsn = "sqlite:///env_test.db"
    monkeypatch.setenv("DATABASE_URL", dsn)

    config = get_alembic_config()

    assert config.get_main_option("sqlalchemy.url") == dsn


def test_get_alembic_config_missing_ini(tmp_path: Path, monkeypatch) -> None:
    import app.db.migrations
    from app.db.migrations import get_alembic_config

    fake_file = str(tmp_path / "fake" / "module.py")
    monkeypatch.setattr(app.db.migrations, "__file__", fake_file)

    with pytest.raises(FileNotFoundError, match=r"alembic\.ini not found"):
        get_alembic_config()


def test_convert_async_dsn_to_sync() -> None:
    from app.db.migrations import _convert_async_dsn_to_sync

    assert _convert_async_dsn_to_sync("sqlite+aiosqlite:///db.sqlite") == "sqlite:///db.sqlite"
    assert (
        _convert_async_dsn_to_sync("postgresql+asyncpg://user:pass@host/db")
        == "postgresql://user:pass@host/db"
    )
    assert _convert_async_dsn_to_sync("sqlite:///db.sqlite") == "sqlite:///db.sqlite"


def test_get_current_revision_without_dsn_or_env(monkeypatch) -> None:
    from app.db.migrations import get_current_revision

    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL not provided"):
        get_current_revision()


def test_run_migrations_with_exception(tmp_path: Path, monkeypatch) -> None:
    from alembic import command

    from app.db.migrations import run_migrations

    db_file = tmp_path / "error_test.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    def mock_upgrade(*args, **kwargs):
        raise RuntimeError("Migration failed")

    monkeypatch.setattr(command, "upgrade", mock_upgrade)

    with pytest.raises(RuntimeError, match="Migration failed"):
        run_migrations(dsn)

    assert "ALEMBIC_SKIP_LOGGING_CONFIG" not in os.environ


def test_run_migrations_offline_mode(tmp_path: Path, capsys) -> None:
    from app.db.migrations import run_migrations

    db_file = tmp_path / "offline_test.sqlite3"
    dsn = f"sqlite+aiosqlite:///{db_file}"

    run_migrations(dsn, offline=True)

    captured = capsys.readouterr()
    assert "CREATE TABLE" in captured.out or "ALTER TABLE" in captured.out or len(captured.out) > 0


def test_check_migrations_needed_with_exception(tmp_path: Path, monkeypatch) -> None:
    from app.db.migrations import check_migrations_needed

    db_file = tmp_path / "exception_test.sqlite3"
    dsn = f"sqlite:///{db_file}"

    def mock_get_revision(*args, **kwargs):
        raise RuntimeError("Cannot get revision")

    monkeypatch.setattr("app.db.migrations.get_current_revision", mock_get_revision)

    assert check_migrations_needed(dsn) is True
