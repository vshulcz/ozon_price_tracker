from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram.types import CallbackQuery, Message, User

from app.i18n import Lang, i18n
from app.repositories.users import PostgresUserRepo

logger = logging.getLogger(__name__)


class ErrorsMiddleware:
    def __init__(self, user_repo: PostgresUserRepo | None = None) -> None:
        self.user_repo = user_repo

    async def __call__(
        self,
        handler: Callable[[Any, Any], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any | None:
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Unhandled error")

        lang: Lang = "ru"
        try:
            repo: PostgresUserRepo | None = data.get("user_repo") or self.user_repo
            user_id = None
            if isinstance(event, Message | CallbackQuery) and isinstance(event.from_user, User):
                user_id = event.from_user.id
            if repo and user_id:
                lang = (await repo.ensure_user(user_id)).language
        except Exception:
            logger.exception("Failed to determine user language")

        text = i18n.t(lang, "error.unexpected")
        try:
            if isinstance(event, CallbackQuery):
                await event.answer("Error", show_alert=False)

                if isinstance(event.message, Message):
                    await event.message.answer(text)

            elif isinstance(event, Message):
                await event.answer(text)
        except Exception:
            logger.exception("Failed to send error message to user")

        return None
