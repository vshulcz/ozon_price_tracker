from typing import Any, cast

import pytest
from conftest import DummyCallbackQuery, DummyMessage

from app.middlewares.errors import ErrorsMiddleware


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


@pytest.mark.asyncio
async def test_errors_middleware_on_message(users_repo, dummy_message, monkeypatch):
    mw = ErrorsMiddleware(session_maker=None)
    monkeypatch.setattr("app.middlewares.errors.Message", DummyMessage, raising=False)

    async def bad_handler(event, data):
        raise RuntimeError("boom")

    res = await mw(bad_handler, dummy_message, {"user_repo": users_repo})
    assert res is None
    assert any("Что-то пошло не так" in a["text"] for a in dummy_message.answers)


@pytest.mark.asyncio
async def test_errors_middleware_on_callback(users_repo, dummy_cb, monkeypatch):
    mw = ErrorsMiddleware(session_maker=None)
    monkeypatch.setattr("app.middlewares.errors.CallbackQuery", DummyCallbackQuery, raising=False)

    async def bad_handler(event, data):
        raise ValueError("bad")

    res = await mw(bad_handler, dummy_cb, {"user_repo": users_repo})
    assert res is None
    assert any(a["text"] == "Error" for a in dummy_cb.answers)


@pytest.mark.asyncio
async def test_errors_middleware_reads_lang_en_on_message(monkeypatch):
    db_session = object()
    session_maker = make_session_maker(db_session)

    class _UserRepoFake:
        def __init__(self, s):
            assert s is db_session

        async def get_by_tg_id(self, tg_id):
            class DTO:
                language = "en"

            return DTO()

    monkeypatch.setattr("app.middlewares.errors.PostgresUserRepo", _UserRepoFake)

    mw = ErrorsMiddleware(session_maker=cast(Any, session_maker))

    msg = DummyMessage(user_id=123)
    monkeypatch.setattr("app.middlewares.errors.Message", DummyMessage, raising=False)

    async def bad_handler(event, data):
        raise RuntimeError("bad")

    res = await mw(bad_handler, msg, {})
    assert res is None
    assert any("Oops! Something went wrong" in a["text"] for a in msg.answers)


@pytest.mark.asyncio
async def test_errors_middleware_fallback_ru_on_session_error(monkeypatch):
    def _broken_maker():
        raise RuntimeError("session fail")

    mw = ErrorsMiddleware(session_maker=cast(Any, _broken_maker))

    msg = DummyMessage(user_id=123)
    monkeypatch.setattr("app.middlewares.errors.Message", DummyMessage, raising=False)

    async def bad_handler(event, data):
        raise RuntimeError("bad")

    res = await mw(bad_handler, msg, {})
    assert res is None
    assert any("Что-то пошло не так" in a["text"] for a in msg.answers)


@pytest.mark.asyncio
async def test_errors_middleware_on_callback_sends_answer_and_message(monkeypatch):
    mw = ErrorsMiddleware(session_maker=None)

    cb = DummyCallbackQuery(user_id=555)
    monkeypatch.setattr("app.middlewares.errors.CallbackQuery", DummyCallbackQuery, raising=False)
    monkeypatch.setattr("app.middlewares.errors.Message", DummyMessage, raising=False)

    async def bad_handler(event, data):
        raise ValueError("bad")

    res = await mw(bad_handler, cb, {})
    assert res is None
    assert any(a["text"] == "Error" for a in cb.answers)
    assert any("Что-то пошло не так" in a["text"] for a in cb.message.answers)
