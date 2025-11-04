from decimal import Decimal

import pytest

from app.handlers.add_product import AddProduct, add_cancel, got_target_price, got_url, start_add
from app.repositories.products import MAX_PRODUCTS_PER_USER


class _PI:
    def __init__(self, title="Item", price_no_card=None, price_with_card=None):
        self.title = title
        self.price_no_card = price_no_card
        self.price_with_card = price_with_card

    @property
    def price_for_compare(self):
        return self.price_with_card or self.price_no_card


@pytest.mark.asyncio
async def test_start_add_under_limit(dummy_cb, users_repo, products_repo, fsm):
    await start_add(dummy_cb, users_repo, products_repo, fsm)
    assert await fsm.get_state() == AddProduct.waiting_for_url.state
    assert "Пришлите ссылку на товар" in dummy_cb.message.edits[-1]["text"]


@pytest.mark.asyncio
async def test_start_add_over_limit(dummy_cb, users_repo, products_repo, fsm):
    u = await users_repo.ensure_user(dummy_cb.from_user.id)
    for i in range(MAX_PRODUCTS_PER_USER):
        await products_repo.create(
            user_id=u.id,
            url=f"https://www.ozon.ru/item/{i}",
            title=f"T{i}",
            target_price=10 + i,
            current_price=None,
        )
    await start_add(dummy_cb, users_repo, products_repo, fsm)
    assert await fsm.get_state() is None
    assert "Достигнут лимит" in dummy_cb.message.edits[-1]["text"]


@pytest.mark.asyncio
async def test_add_cancel(dummy_cb, users_repo, fsm):
    await fsm.set_state(AddProduct.waiting_for_url)
    await add_cancel(dummy_cb, users_repo, fsm)
    assert await fsm.get_state() is None
    assert "Добавление отменено" in dummy_cb.message.edits[-1]["text"]


@pytest.mark.asyncio
async def test_got_url_invalid(dummy_message, users_repo, products_repo, fsm):
    await fsm.set_state(AddProduct.waiting_for_url)
    dummy_message.text = "https://example.com/not-ozon"
    await got_url(dummy_message, users_repo, products_repo, fsm)
    assert any("это не ссылка Ozon" in a["text"] for a in dummy_message.answers)
    assert await fsm.get_state() == AddProduct.waiting_for_url.state


@pytest.mark.asyncio
async def test_got_url_duplicate(dummy_message, users_repo, products_repo, fsm):
    u = await users_repo.ensure_user(dummy_message.from_user.id)
    url = "https://www.ozon.ru/item/42"
    await products_repo.create(
        user_id=u.id, url=url, title="Exists", target_price=10, current_price=None
    )

    await fsm.set_state(AddProduct.waiting_for_url)
    dummy_message.text = url
    await got_url(dummy_message, users_repo, products_repo, fsm)
    assert any("уже добавлен" in a["text"] for a in dummy_message.answers)
    assert await fsm.get_state() is None


@pytest.mark.asyncio
async def test_got_url_fetch_blocked(monkeypatch, dummy_message, users_repo, products_repo, fsm):
    await fsm.set_state(AddProduct.waiting_for_url)
    dummy_message.text = "https://www.ozon.ru/item/100"

    async def _blocked(url):
        raise RuntimeError("blocked")

    monkeypatch.setattr("app.handlers.add_product.fetch_product_info", _blocked)

    await got_url(dummy_message, users_repo, products_repo, fsm)
    assert dummy_message.children, "ожидали временное сообщение"
    temp = dummy_message.children[-1]
    assert temp.edits and any("блокирует доступ" in e["text"] for e in temp.edits)


@pytest.mark.asyncio
async def test_got_url_fetch_error(monkeypatch, dummy_message, users_repo, products_repo, fsm):
    await fsm.set_state(AddProduct.waiting_for_url)
    dummy_message.text = "https://www.ozon.ru/item/101"

    async def _error(url):
        raise Exception("any")

    monkeypatch.setattr("app.handlers.add_product.fetch_product_info", _error)

    await got_url(dummy_message, users_repo, products_repo, fsm)
    temp = dummy_message.children[-1]
    assert temp.edits and any("Не удалось получить данные" in e["text"] for e in temp.edits)  # noqa: RUF001


@pytest.mark.asyncio
async def test_got_url_success_to_wait_target(
    monkeypatch, dummy_message, users_repo, products_repo, fsm
):
    await fsm.set_state(AddProduct.waiting_for_url)
    dummy_message.text = "https://www.ozon.ru/item/102"

    async def _ok(url):
        return _PI(title="Chair", price_no_card=Decimal("123.45"), price_with_card=None)

    monkeypatch.setattr("app.handlers.add_product.fetch_product_info", _ok)

    await got_url(dummy_message, users_repo, products_repo, fsm)

    edited_children = [c for c in dummy_message.children if c.edits]
    assert edited_children, "ожидали редактирование временного сообщения"
    assert "Chair" in edited_children[-1].edits[-1]["text"]

    assert await fsm.get_state() == AddProduct.waiting_for_target_price.state
    assert any("Укажите целевую цену" in a["text"] for a in dummy_message.answers)


@pytest.mark.asyncio
async def test_got_target_price_invalid(dummy_message, users_repo, products_repo, fsm):
    await fsm.set_state(AddProduct.waiting_for_target_price)
    dummy_message.text = "abc"
    await got_target_price(dummy_message, users_repo, products_repo, fsm)
    assert any("Введите корректное" in a["text"] for a in dummy_message.answers)
    assert await fsm.get_state() == AddProduct.waiting_for_target_price.state


@pytest.mark.asyncio
async def test_got_target_price_success(dummy_message, users_repo, products_repo, fsm):
    await fsm.set_state(AddProduct.waiting_for_target_price)
    await fsm.update_data(
        url="https://www.ozon.ru/item/103", title="Lamp", current_price=str(Decimal("99.99"))
    )
    dummy_message.text = "88.80"

    await got_target_price(dummy_message, users_repo, products_repo, fsm)
    assert any("Готово! Товар сохранён" in a["text"] for a in dummy_message.answers)
    assert await fsm.get_state() is None

    u = await users_repo.ensure_user(dummy_message.from_user.id)
    existing = await products_repo.get_by_url(u.id, "https://www.ozon.ru/item/103")
    assert existing is not None
    latest = await products_repo.get_latest_price(existing.id)
    assert latest and latest[0] == 99.99
