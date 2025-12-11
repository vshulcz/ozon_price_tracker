import asyncio
from typing import Any, cast

import pytest

import app.bot as botmod
from app.middlewares.db_session import DBSessionMiddleware


class _Sentinel:
    pass


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _FakeSession:
    pass


class _SessionCtx:
    def __init__(self, session) -> None:
        self._s = session

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, exc_type, exc, tb):
        return False


def make_session_maker(session):
    def _maker():
        return _SessionCtx(session)

    return _maker


class _Pipe:
    def __init__(self) -> None:
        self.middlewares = []

    def middleware(self, mw) -> None:
        self.middlewares.append(mw)


class FakeDispatcher:
    def __init__(self, storage=None) -> None:
        self.storage = storage
        self.message = _Pipe()
        self.callback_query = _Pipe()
        self.included = []
        self.poll_started = False

    def include_router(self, router) -> None:
        self.included.append(router)

    async def start_polling(self, bot) -> None:
        self.poll_started = True
        await asyncio.sleep(0)


class _FakeBotSession:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeBot:
    def __init__(self, token, default) -> None:
        self.token = token
        self.default = default
        self.deleted_webhook = None
        self.commands_set = None
        self.session = _FakeBotSession()

    async def delete_webhook(self, drop_pending_updates=False) -> None:
        self.deleted_webhook = {"drop_pending_updates": drop_pending_updates}

    async def set_my_commands(self, commands) -> None:
        self.commands_set = list(commands)


class FakeScheduler:
    def __init__(self) -> None:
        self.shutdown_called = False
        self.kwargs = None

    def shutdown(self, wait=False) -> None:
        self.shutdown_called = True
        self.kwargs = {"wait": wait}


@pytest.mark.asyncio
async def test_db_session_middleware_injects_fresh_repos(monkeypatch):
    session = _FakeSession()
    session_maker = make_session_maker(session)
    created = {}

    class _UserRepoFake:
        def __init__(self, s):
            created["user_repo_session"] = s
            self.session = s

    class _ProductsRepoFake:
        def __init__(self, s):
            created["products_repo_session"] = s
            self.session = s

    monkeypatch.setattr("app.middlewares.db_session.PostgresUserRepo", _UserRepoFake)
    monkeypatch.setattr("app.middlewares.db_session.ProductsRepo", _ProductsRepoFake)

    mw = DBSessionMiddleware(cast(Any, session_maker))

    async def handler(event, data):
        assert "user_repo" in data and "products" in data
        assert data["user_repo"].session is session
        assert data["products"].session is session
        return _Sentinel

    res = await mw(handler, event={"any": "thing"}, data={})
    assert res is _Sentinel
    assert created["user_repo_session"] is session
    assert created["products_repo_session"] is session


@pytest.mark.asyncio
async def test_setup_bot_commands_sets_two_commands() -> None:
    fb = FakeBot("TOKEN", default=None)
    await botmod.setup_bot_commands(cast(Any, fb))

    assert fb.commands_set is not None and len(fb.commands_set) == 2
    cmds = {c.command: c.description for c in fb.commands_set}
    assert cmds.get("start") == "Start / Запуск"
    assert cmds.get("menu") == "Main menu / Главное меню"


@pytest.mark.asyncio
async def test_main_wires_everything_and_cleans_up(monkeypatch):
    class _S:
        bot_token = "TEST:TOKEN"  # noqa: S105
        database_url = "sqlite+aiosqlite:///file.db"
        log_level = "INFO"
        price_check_hours = "1,2,3"
        auto_migrate = True
        metrics_enabled: bool = True
        metrics_host: str = "0.0.0.0"  # noqa: S104
        metrics_port: int = 8000

    monkeypatch.setattr(botmod.Settings, "from_env", staticmethod(lambda: _S))

    engine = FakeEngine()
    session = _FakeSession()
    session_maker = make_session_maker(session)

    def _init_engine_and_schema(db_url):
        assert db_url == _S.database_url
        return engine, session_maker

    monkeypatch.setattr(botmod, "init_engine_and_schema", _init_engine_and_schema)

    monkeypatch.setattr(botmod, "Bot", FakeBot)
    monkeypatch.setattr(botmod, "Dispatcher", FakeDispatcher)

    scheduler = FakeScheduler()

    def _setup_scheduler(bot, price_check_hours, session_maker_arg):
        assert bot.token == _S.bot_token
        assert session_maker_arg is session_maker
        assert price_check_hours == _S.price_check_hours
        return scheduler

    monkeypatch.setattr(botmod, "setup_scheduler", _setup_scheduler)

    called = {"shutdown_browser": 0}

    async def _shutdown_browser() -> None:
        called["shutdown_browser"] += 1

    monkeypatch.setattr(botmod, "shutdown_browser", _shutdown_browser)

    included = []

    orig_include_router = FakeDispatcher.include_router

    def _spy_include_router(self, router):
        included.append(router)
        return orig_include_router(self, router)

    monkeypatch.setattr(FakeDispatcher, "include_router", _spy_include_router, raising=False)

    await botmod.main()

    assert len(included) == 4

    FakeDispatcher()

    assert scheduler.shutdown_called is True and scheduler.kwargs == {"wait": False}
    assert called["shutdown_browser"] == 1
    assert engine.disposed is True
