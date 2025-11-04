import pytest

from app.config import Settings


def test_settings_from_env_ok(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///file.db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = Settings.from_env()
    assert s.bot_token == "123:ABC"  # noqa: S105
    assert s.database_url.startswith("sqlite+aiosqlite://")
    assert s.log_level == "DEBUG"


def test_settings_from_env_missing_token(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///file.db")
    with pytest.raises(RuntimeError) as e:
        Settings.from_env()
    assert "BOT_TOKEN is not set" in str(e.value)


def test_settings_from_env_missing_db(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123:ABC")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError) as e:
        Settings.from_env()
    assert "DATABASE_URL is not set" in str(e.value)
