import pytest
from conftest import DummyCallbackQuery, DummyMessage

from app.middlewares.errors import ErrorsMiddleware


@pytest.mark.asyncio
async def test_errors_middleware_on_message(users_repo, dummy_message, monkeypatch):
    mw = ErrorsMiddleware(user_repo=users_repo)
    monkeypatch.setattr("app.middlewares.errors.Message", DummyMessage, raising=False)

    async def bad_handler(event, data):
        raise RuntimeError("boom")

    res = await mw(bad_handler, dummy_message, {"user_repo": users_repo})
    assert res is None
    assert any("Что-то пошло не так" in a["text"] for a in dummy_message.answers)


@pytest.mark.asyncio
async def test_errors_middleware_on_callback(users_repo, dummy_cb, monkeypatch):
    mw = ErrorsMiddleware(user_repo=users_repo)
    monkeypatch.setattr("app.middlewares.errors.CallbackQuery", DummyCallbackQuery, raising=False)

    async def bad_handler(event, data):
        raise ValueError("bad")

    res = await mw(bad_handler, dummy_cb, {"user_repo": users_repo})
    assert res is None
    assert any(a["text"] == "Error" for a in dummy_cb.answers)
