from decimal import Decimal
from typing import Any, cast

import pytest

from app.repositories.products import ProductsRepo
from app.repositories.users import PostgresUserRepo
from app.scheduler import refresh_prices_and_notify


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
async def test_scheduler_deal_transitions(
    fake_bot, users_repo: PostgresUserRepo, products_repo: ProductsRepo, session, monkeypatch
):
    db_session = session
    user = await users_repo.ensure_user(777)
    pid = await products_repo.create(
        user_id=user.id,
        url="https://www.ozon.ru/item/100",
        title="Cool Thing",
        target_price=100.00,
        current_price=150.00,
    )

    async def _only_one():
        p = await products_repo.get_by_id(pid)
        assert p is not None
        yield p

    monkeypatch.setattr(products_repo, "list_all_active", _only_one)

    async def fake_fetch(url: str):
        from app.services.ozon_client import ProductInfo

        return ProductInfo(title="Cool Thing", price_no_card=Decimal("95.00"), price_with_card=None)

    monkeypatch.setattr("app.scheduler.fetch_product_info", fake_fetch)

    class _UsersRepoFactory:
        def __init__(self, inst):
            self.inst = inst

        def __call__(self, session):
            assert session is db_session
            return self.inst

    class _ProductsRepoFactory:
        def __init__(self, inst):
            self.inst = inst

        def __call__(self, session):
            assert session is db_session
            return self.inst

    monkeypatch.setattr("app.scheduler.PostgresUserRepo", _UsersRepoFactory(users_repo))
    monkeypatch.setattr("app.scheduler.ProductsRepo", _ProductsRepoFactory(products_repo))

    session_maker = make_session_maker(db_session)

    await refresh_prices_and_notify(fake_bot, cast(Any, session_maker))
    assert len(fake_bot.messages) == 1
    assert (
        "достиг целевой цены" in fake_bot.messages[0]["text"]
        or "reached the target" in fake_bot.messages[0]["text"]
    )

    latest = await products_repo.get_latest_price(pid)
    assert latest and latest[0] == 95.00

    async def fake_fetch_high(url: str):
        from app.services.ozon_client import ProductInfo

        return ProductInfo(
            title="Cool Thing", price_no_card=Decimal("130.00"), price_with_card=None
        )

    monkeypatch.setattr("app.scheduler.fetch_product_info", fake_fetch_high)

    await refresh_prices_and_notify(fake_bot, cast(Any, session_maker))
    assert len(fake_bot.messages) == 2
    assert (
        "снова выше цели" in fake_bot.messages[1]["text"]
        or "no longer below target" in fake_bot.messages[1]["text"]
    )
