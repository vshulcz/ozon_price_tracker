from __future__ import annotations

import logging
from typing import cast

from aiogram import F, Router
from aiogram.types import CallbackQuery, InaccessibleMessage

from app.callbacks import MenuCB, SettingsCB
from app.i18n import Lang, i18n
from app.keyboards.main import main_menu_kb, settings_kb
from app.repositories.users import PostgresUserRepo
from app.utils.logging import log_callback_handler

logger = logging.getLogger(__name__)

router = Router(name="settings")


@router.callback_query(MenuCB.filter(F.action == "settings"))
@log_callback_handler("settings_open")
async def open_settings(cb: CallbackQuery, user_repo: PostgresUserRepo) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    text = f"<b>{i18n.t(user.language, 'settings.title')}</b>\n\n"
    text += f"{i18n.t(user.language, 'settings.choose_lang')}"

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    await cb.message.edit_text(text, reply_markup=settings_kb(i18n, user.language))
    await cb.answer()


@router.callback_query(SettingsCB.filter(F.action == "lang"))
@log_callback_handler("settings_change_lang")
async def change_lang(
    cb: CallbackQuery, callback_data: SettingsCB, user_repo: PostgresUserRepo
) -> None:
    await user_repo.ensure_user(cb.from_user.id)
    raw = callback_data.value or "ru"
    new_lang: Lang = cast(Lang, raw if raw in ("ru", "en") else "ru")
    await user_repo.set_language(cb.from_user.id, new_lang)

    logger.info(
        "User %d changed language to: %s",
        cb.from_user.id,
        new_lang,
    )

    lang_name = "Русский" if new_lang == "ru" else "English"

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    await cb.message.edit_text(
        i18n.t(new_lang, "settings.lang.changed", lang_name=lang_name),
        reply_markup=main_menu_kb(i18n, new_lang),
    )
    await cb.answer()


@router.callback_query(SettingsCB.filter(F.action == "back"))
async def settings_back(cb: CallbackQuery, user_repo: PostgresUserRepo) -> None:
    lang = await user_repo.get_language(cb.from_user.id)
    text = f"<b>{i18n.t(lang, 'start.title')}</b>\n\n" + i18n.t(lang, "start.body")

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    await cb.message.edit_text(text, reply_markup=main_menu_kb(i18n, lang))
    await cb.answer()
