from typing import Any, cast

import pytest

from app.middlewares.db_session import DBSessionMiddleware


class _FakeSession:
    def __init__(self):
        self.rollback_called = 0

    async def rollback(self):
        self.rollback_called += 1


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
async def test_db_session_middleware_rolls_back_on_exception(monkeypatch):
    session = _FakeSession()
    session_maker = make_session_maker(session)

    class _UserRepoFake:
        def __init__(self, s):
            pass

    class _ProductsRepoFake:
        def __init__(self, s):
            pass

    monkeypatch.setattr("app.middlewares.db_session.PostgresUserRepo", _UserRepoFake)
    monkeypatch.setattr("app.middlewares.db_session.ProductsRepo", _ProductsRepoFake)

    mw = DBSessionMiddleware(cast(Any, session_maker))

    async def bad_handler(event, data):
        raise RuntimeError("fail inside handler")

    with pytest.raises(RuntimeError):
        await mw(bad_handler, event={"e": 1}, data={})

    assert session.rollback_called == 1
