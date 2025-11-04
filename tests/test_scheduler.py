from decimal import Decimal

import pytest

from app.repositories.products import ProductsRepo
from app.repositories.users import PostgresUserRepo
from app.scheduler import refresh_prices_and_notify


@pytest.mark.asyncio
async def test_scheduler_deal_transitions(
    fake_bot, users_repo: PostgresUserRepo, products_repo: ProductsRepo, monkeypatch
):
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

    await refresh_prices_and_notify(fake_bot, users_repo, products_repo)
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

    await refresh_prices_and_notify(fake_bot, users_repo, products_repo)
    assert len(fake_bot.messages) == 2
    assert (
        "снова выше цели" in fake_bot.messages[1]["text"]
        or "no longer below target" in fake_bot.messages[1]["text"]
    )
