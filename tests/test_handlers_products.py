from typing import Any, cast

import pytest
from conftest import DummyCallbackQuery, DummyMessage

from app.callbacks import MenuCB, ProductCB
from app.handlers.products import (
    EditTarget,
    _fmt_price,
    _render_product,
    back_to_list,
    delete_product,
    edit_target_cancel,
    edit_target_save,
    edit_target_start,
    open_list,
    open_product,
)
from app.repositories.products import PAGE_SIZE


@pytest.mark.asyncio
async def test_open_list_empty(dummy_cb, users_repo, products_repo):
    from conftest import DummyCallbackQuery

    cb = DummyCallbackQuery(user_id=987654321)
    await open_list(cb, MenuCB(action="list"), users_repo, products_repo)
    assert cb.message.edits
    assert "У вас пока нет товаров" in cb.message.edits[-1]["text"]  # noqa: RUF001


@pytest.mark.asyncio
async def test_open_list_with_items(dummy_cb, users_repo, products_repo):
    u = await users_repo.ensure_user(dummy_cb.from_user.id)
    for i in range(3):
        await products_repo.create(
            user_id=u.id,
            url=f"https://www.ozon.ru/item/{i}",
            title=f"T{i}",
            target_price=10 + i,
            current_price=20 + i,
        )
    await open_list(dummy_cb, MenuCB(action="list", page=1), users_repo, products_repo)
    assert dummy_cb.message.edits
    assert "Ваши товары" in dummy_cb.message.edits[-1]["text"]


@pytest.mark.asyncio
async def test_open_product(users_repo, products_repo):
    cb = DummyCallbackQuery(user_id=555123)
    u = await users_repo.ensure_user(cb.from_user.id)

    pid = await products_repo.create(
        user_id=u.id,
        url="https://www.ozon.ru/item/unique-1",
        title="Phone",
        target_price=100,
        current_price=120,
    )
    await products_repo.add_price_history(pid, 119.99, source="add")

    await open_product(cb, ProductCB(action="open", id=pid, page=1), users_repo, products_repo)

    texts = []
    texts += [e["text"] for e in cb.message.edits if e["text"]]
    texts += [a["text"] for a in cb.answers if a["text"]]

    assert texts, f"нет текста в edits/answers: edits={cb.message.edits} answers={cb.answers}"
    text = texts[-1]
    assert "Карточка товара" in text
    assert "Phone" in text
    assert "119.99" in text


@pytest.mark.asyncio
async def test_edit_target_start_and_cancel(dummy_cb, users_repo, products_repo, fsm):
    u = await users_repo.ensure_user(dummy_cb.from_user.id)
    pid = await products_repo.create(
        user_id=u.id,
        url="https://www.ozon.ru/item/2",
        title="Mouse",
        target_price=50,
        current_price=55,
    )

    await edit_target_start(dummy_cb, ProductCB(action="edit", id=pid, page=2), users_repo, fsm)
    assert await fsm.get_state() == EditTarget.waiting_for_price.state
    assert "Введите новую целевую цену" in dummy_cb.message.edits[-1]["text"]

    await edit_target_cancel(dummy_cb, users_repo, products_repo, fsm)
    assert await fsm.get_state() is None

    texts = [e["text"] for e in dummy_cb.message.edits if e["text"]] + [
        a["text"] for a in dummy_cb.answers if a["text"]
    ]
    assert any("Карточка товара" in t for t in texts)


@pytest.mark.asyncio
async def test_edit_target_save(dummy_message, users_repo, products_repo, fsm, monkeypatch):
    u = await users_repo.ensure_user(dummy_message.from_user.id)
    pid = await products_repo.create(
        user_id=u.id,
        url="https://www.ozon.ru/item/3",
        title="Keyboard",
        target_price=200,
        current_price=210,
    )

    await fsm.set_state(EditTarget.waiting_for_price)
    await fsm.update_data(product_id=pid, page=1)
    dummy_message.text = "149.90"

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.handlers.products._render_product", _noop)

    await edit_target_save(dummy_message, users_repo, products_repo, fsm)

    assert any("Целевая цена обновлена" in a["text"] for a in dummy_message.answers)
    prod = await products_repo.get_by_id(pid)
    assert prod.target_price == 149.90


@pytest.mark.asyncio
async def test_delete_product(dummy_cb, users_repo, products_repo):
    u = await users_repo.ensure_user(dummy_cb.from_user.id)
    pid = await products_repo.create(
        user_id=u.id,
        url="https://www.ozon.ru/item/4",
        title="SSD",
        target_price=99.0,
        current_price=None,
    )
    await delete_product(
        dummy_cb, ProductCB(action="delete", id=pid, page=1), users_repo, products_repo
    )
    assert "Товар удалён" in dummy_cb.message.edits[-1]["text"]
    assert await products_repo.get_by_id(pid) is None


@pytest.mark.asyncio
async def test_open_list_with_items_and_pagination(users_repo, products_repo):
    cb = DummyCallbackQuery(user_id=987654320)
    u = await users_repo.ensure_user(cb.from_user.id)

    total = PAGE_SIZE + 2
    for i in range(total):
        await products_repo.create(
            user_id=u.id,
            url=f"https://www.ozon.ru/item/p{i}",
            title=f"Item {i}",
            target_price=100 + i,
            current_price=100 + i,
        )

    await open_list(cb, MenuCB(action="list", page=2), users_repo, products_repo)
    assert cb.message.edits
    text = cb.message.edits[-1]["text"]
    assert "Ваши товары" in text and "стр. 2/2" in text


def _last_text_from(cb):
    texts = [e["text"] for e in cb.message.edits if e["text"]]
    texts += [a["text"] for a in cb.answers if a["text"]]
    return texts[-1] if texts else None


def test_fmt_price_formats_and_dash():
    assert _fmt_price(12.3) == "12.30"
    assert _fmt_price(None) == "—"


@pytest.mark.asyncio
async def test_open_list_empty_separately(users_repo, products_repo):
    cb = DummyCallbackQuery(user_id=111222333)
    await open_list(cb, MenuCB(action="list", page=1), users_repo, products_repo)
    assert cb.message.edits
    assert "У вас пока нет товаров" in cb.message.edits[-1]["text"]  # noqa: RUF001


@pytest.mark.asyncio
async def test_render_product_not_found_for_callback(users_repo, products_repo):
    cb = DummyCallbackQuery(user_id=444555666)
    u = await users_repo.ensure_user(cb.from_user.id)
    await _render_product(
        cast(Any, cb), lang=u.language, product_id=999999, page=1, products=products_repo
    )
    assert any(a["text"] == "Not found" for a in cb.answers)


@pytest.mark.asyncio
async def test_render_product_not_found_for_message(users_repo, products_repo):
    msg = DummyMessage(user_id=777888999)
    await _render_product(
        cast(Any, msg), lang="ru", product_id=123456, page=1, products=products_repo
    )
    assert any(a["text"] == "Not found" for a in msg.answers)


@pytest.mark.asyncio
async def test_open_product_with_latest_price(users_repo, products_repo):
    cb = DummyCallbackQuery(user_id=555123777)
    u = await users_repo.ensure_user(cb.from_user.id)
    pid = await products_repo.create(
        user_id=u.id,
        url="https://www.ozon.ru/item/unique-xyz",
        title="Gadget",
        target_price=50,
        current_price=60,
    )
    await products_repo.add_price_history(pid, 49.99, source="add")

    await open_product(cb, ProductCB(action="open", id=pid, page=1), users_repo, products_repo)
    text = _last_text_from(cb)
    assert text and "Карточка товара" in text and "Gadget" in text and "49.99" in text


@pytest.mark.asyncio
async def test_back_to_list_displays_page(users_repo, products_repo):
    cb = DummyCallbackQuery(user_id=888000111)
    u = await users_repo.ensure_user(cb.from_user.id)
    for i in range(PAGE_SIZE):
        await products_repo.create(
            user_id=u.id,
            url=f"https://www.ozon.ru/item/b{i}",
            title=f"B{i}",
            target_price=10 + i,
            current_price=10 + i,
        )

    await back_to_list(cb, ProductCB(action="back", id=1, page=1), users_repo, products_repo)
    assert cb.message.edits
    assert "Ваши товары (стр. 1/1)" in cb.message.edits[-1]["text"]


@pytest.mark.asyncio
async def test_edit_target_start_sets_state_and_prompts(users_repo, products_repo, fsm):
    cb = DummyCallbackQuery(user_id=999111222)
    u = await users_repo.ensure_user(cb.from_user.id)
    pid = await products_repo.create(
        user_id=u.id,
        url="https://www.ozon.ru/item/et1",
        title="ET1",
        target_price=100,
        current_price=120,
    )

    await edit_target_start(cb, ProductCB(action="edit", id=pid, page=3), users_repo, fsm)
    assert await fsm.get_state() == EditTarget.waiting_for_price.state
    assert "Введите новую целевую цену" in cb.message.edits[-1]["text"]


@pytest.mark.asyncio
async def test_edit_target_cancel_missing_product_id(users_repo, products_repo, fsm):
    cb = DummyCallbackQuery(user_id=999222333)
    await users_repo.ensure_user(cb.from_user.id)

    await fsm.set_state(EditTarget.waiting_for_price)
    await edit_target_cancel(cb, users_repo, products_repo, fsm)
    assert await fsm.get_state() is None
    assert any(a["text"] == "Product ID not found" for a in cb.answers)


@pytest.mark.asyncio
async def test_edit_target_save_invalid_price(users_repo, products_repo, fsm):
    msg = DummyMessage(user_id=1010101010)
    u = await users_repo.ensure_user(msg.from_user.id)
    pid = await products_repo.create(
        user_id=u.id,
        url="https://www.ozon.ru/item/et2",
        title="ET2",
        target_price=200,
        current_price=210,
    )

    await fsm.set_state(EditTarget.waiting_for_price)
    await fsm.update_data(product_id=pid, page=1)
    msg.text = "не число"

    await edit_target_save(msg, users_repo, products_repo, fsm)
    assert any("Введите корректное" in a["text"] for a in msg.answers)
    assert await fsm.get_state() == EditTarget.waiting_for_price.state


@pytest.mark.asyncio
async def test_edit_target_save_missing_product_id(users_repo, fsm):
    msg = DummyMessage(user_id=2020202020)
    await users_repo.ensure_user(msg.from_user.id)
    await fsm.set_state(EditTarget.waiting_for_price)
    msg.text = "123.45"

    from app.repositories.products import ProductsRepo

    dummy_products = ProductsRepo

    await edit_target_save(msg, users_repo, dummy_products, fsm)
    assert any("Product ID not found" in a["text"] for a in msg.answers)


@pytest.mark.asyncio
async def test_delete_product_not_found_or_foreign(users_repo, products_repo):
    cb = DummyCallbackQuery(user_id=3030303030)
    _ = await users_repo.ensure_user(cb.from_user.id)

    u_b_id = 4040404040
    u_b = await users_repo.ensure_user(u_b_id)
    pid = await products_repo.create(
        user_id=u_b.id,
        url="https://www.ozon.ru/item/foreign",
        title="Foreign",
        target_price=10,
        current_price=15,
    )

    await delete_product(cb, ProductCB(action="delete", id=999999), users_repo, products_repo)
    assert any(a["text"] == "Not found" for a in cb.answers)

    await delete_product(cb, ProductCB(action="delete", id=pid), users_repo, products_repo)
    assert any(a["text"] == "Not found" for a in cb.answers)


@pytest.mark.asyncio
async def test_delete_product_success(users_repo, products_repo):
    cb = DummyCallbackQuery(user_id=5050505050)
    u = await users_repo.ensure_user(cb.from_user.id)
    pid = await products_repo.create(
        user_id=u.id,
        url="https://www.ozon.ru/item/del-ok",
        title="DelOK",
        target_price=10,
        current_price=15,
    )

    await delete_product(cb, ProductCB(action="delete", id=pid), users_repo, products_repo)
    assert cb.message.edits
    assert "Товар удалён" in cb.message.edits[-1]["text"]

    assert (await products_repo.get_by_id(pid)) is None
