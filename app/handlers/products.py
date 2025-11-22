from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from app.callbacks import ActionCB, MenuCB, ProductCB
from app.i18n import Lang, i18n
from app.keyboards.common import cancel_kb
from app.keyboards.products import product_card_kb, products_list_kb
from app.repositories.products import PAGE_SIZE, ProductsRepo
from app.repositories.users import PostgresUserRepo
from app.utils.logging import log_callback_handler, log_message_handler, log_product_action
from app.utils.validators import parse_price

router = Router(name="products")


class EditTarget(StatesGroup):
    waiting_for_price = State()


def _fmt_price(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else "—"


@router.callback_query(MenuCB.filter(F.action == "list"))
@log_callback_handler("products_list")
async def open_list(
    cb: CallbackQuery,
    callback_data: MenuCB,
    user_repo: PostgresUserRepo,
    products: ProductsRepo,
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    if isinstance(cb.message, InaccessibleMessage | None):
        return

    page = callback_data.page or 1
    items, pages = await products.list_page(user.id, page, PAGE_SIZE)

    log_product_action(
        user.id, "view_products_list", page=page, total_pages=pages, items_count=len(items)
    )

    if not items:
        await cb.message.edit_text(
            i18n.t(user.language, "list.empty"),
            reply_markup=products_list_kb(i18n, user.language, items=[], page=1, pages=1),
        )
        await cb.answer()
        return

    pairs = [
        (
            p.id,
            i18n.t(
                user.language,
                "list.item",
                title=p.title,
                price=_fmt_price(p.current_price),
            ),
        )
        for p in items
    ]
    await cb.message.edit_text(
        i18n.t(user.language, "list.title", page=page, pages=pages),
        reply_markup=products_list_kb(i18n, user.language, items=pairs, page=page, pages=pages),
    )
    await cb.answer()


async def _render_product(
    cb: Any,
    *,
    lang: Lang,
    product_id: int,
    page: int,
    products: ProductsRepo,
) -> None:
    prod = await products.get_by_id(product_id)
    if not prod:
        if isinstance(cb, CallbackQuery):
            await cb.answer("Not found", show_alert=True)
        else:
            await cb.answer("Not found")
        return

    latest = await products.get_latest_price(prod.id)
    date_part = i18n.t(lang, "product.curr.date", date=latest[1]) if latest else ""
    current_price = latest[0] if latest else prod.current_price

    text = f"""<b>{i18n.t(lang, "product.title")}</b>

{i18n.t(lang, "product.name", title=prod.title)}
{i18n.t(lang, "product.link", url=f'<a href="{prod.url}">{prod.url}</a>')}
{i18n.t(lang, "product.curr", price=_fmt_price(current_price), date_part=date_part)}
{i18n.t(lang, "product.target", price=_fmt_price(prod.target_price))}"""

    if isinstance(cb, CallbackQuery) and not isinstance(cb.message, InaccessibleMessage | None):
        await cb.message.edit_text(
            text,
            reply_markup=product_card_kb(i18n, lang, product_id=prod.id, page=page, url=prod.url),
        )
    else:
        await cb.answer(text)


@router.callback_query(ProductCB.filter(F.action == "open"))
@log_callback_handler("product_open")
async def open_product(
    cb: CallbackQuery,
    callback_data: ProductCB,
    user_repo: PostgresUserRepo,
    products: ProductsRepo,
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    log_product_action(user.id, "view_product_details", product_id=callback_data.id)
    await _render_product(
        cb,
        lang=user.language,
        product_id=callback_data.id,
        page=callback_data.page or 1,
        products=products,
    )
    await cb.answer()


@router.callback_query(ProductCB.filter(F.action == "back"))
async def back_to_list(
    cb: CallbackQuery,
    callback_data: ProductCB,
    user_repo: PostgresUserRepo,
    products: ProductsRepo,
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    if isinstance(cb.message, InaccessibleMessage | None):
        return

    page = callback_data.page or 1
    items, pages = await products.list_page(user.id, page, PAGE_SIZE)
    pairs = [
        (
            p.id,
            i18n.t(
                user.language,
                "list.item",
                title=p.title,
                price=_fmt_price(p.current_price),
            ),
        )
        for p in items
    ]
    await cb.message.edit_text(
        i18n.t(user.language, "list.title", page=page, pages=pages),
        reply_markup=products_list_kb(i18n, user.language, items=pairs, page=page, pages=pages),
    )
    await cb.answer()


@router.callback_query(ProductCB.filter(F.action == "edit"))
@log_callback_handler("product_edit_start")
async def edit_target_start(
    cb: CallbackQuery,
    callback_data: ProductCB,
    user_repo: PostgresUserRepo,
    state: FSMContext,
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    if isinstance(cb.message, InaccessibleMessage | None):
        return

    log_product_action(user.id, "start_edit_target_price", product_id=callback_data.id)

    await state.set_state(EditTarget.waiting_for_price)
    await state.update_data(product_id=callback_data.id, page=callback_data.page or 1)
    await cb.message.edit_text(
        i18n.t(user.language, "edit.ask"), reply_markup=cancel_kb(i18n, user.language)
    )
    await cb.answer()


@router.callback_query(ActionCB.filter(F.action == "cancel"), EditTarget.waiting_for_price)
async def edit_target_cancel(
    cb: CallbackQuery,
    user_repo: PostgresUserRepo,
    products: ProductsRepo,
    state: FSMContext,
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    data = await state.get_data()
    await state.clear()
    product_id_raw = data.get("product_id")
    page_raw = data.get("page", 1)
    if product_id_raw is None:
        await cb.answer("Product ID not found", show_alert=True)
        return

    await _render_product(
        cb,
        lang=user.language,
        product_id=int(product_id_raw),
        page=int(page_raw),
        products=products,
    )
    await cb.answer(i18n.t(user.language, "edit.cancel"))


@router.message(EditTarget.waiting_for_price)
@log_message_handler("product_edit_save")
async def edit_target_save(
    message: Message,
    user_repo: PostgresUserRepo,
    products: ProductsRepo,
    state: FSMContext,
) -> None:
    from_user = message.from_user
    if from_user is None:
        return

    user = await user_repo.ensure_user(from_user.id)
    price = parse_price(message.text or "")
    if price is None:
        log_product_action(user.id, "invalid_edit_price", text=(message.text or "")[:50])
        await message.answer(
            i18n.t(user.language, "add.invalid_price"),
            reply_markup=cancel_kb(i18n, user.language),
        )
        return

    data = await state.get_data()
    product_id_raw = data.get("product_id")
    if product_id_raw is None:
        await message.answer("Product ID not found", reply_markup=cancel_kb(i18n, user.language))
        return

    product_id = int(product_id_raw)
    page = int(data.get("page", 1))

    await products.update_target_price(product_id, float(price))

    log_product_action(
        user.id, "updated_target_price", product_id=product_id, new_target=float(price)
    )

    await state.clear()

    await message.answer(i18n.t(user.language, "edit.saved", price=f"{price:.2f}"))

    class _MsgAdapter:
        def __init__(self, msg: Message) -> None:
            self._msg = msg

        async def answer(self, *args: Any, **kwargs: Any) -> None:
            await self._msg.answer(*args, **kwargs)

    await _render_product(
        _MsgAdapter(message),
        lang=user.language,
        product_id=product_id,
        page=page,
        products=products,
    )


@router.callback_query(ProductCB.filter(F.action == "delete"))
@log_callback_handler("product_delete")
async def delete_product(
    cb: CallbackQuery,
    callback_data: ProductCB,
    user_repo: PostgresUserRepo,
    products: ProductsRepo,
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    prod = await products.get_by_id(callback_data.id)

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    if not prod or prod.user_id != user.id:
        await cb.answer("Not found", show_alert=True)
        return

    log_product_action(user.id, "deleted_product", product_id=prod.id, title=prod.title[:50])

    await products.delete(prod.id)
    await cb.message.edit_text(i18n.t(user.language, "notif.delete.ok"))
    await cb.answer()
