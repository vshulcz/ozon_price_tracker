from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram.types import CallbackQuery, Message, User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.i18n import Lang, i18n
from app.repositories.users import PostgresUserRepo

logger = logging.getLogger(__name__)


class ErrorsMiddleware:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession] | None = None) -> None:
        self.session_maker = session_maker

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
            tg_id = None
            if isinstance(event, (Message, CallbackQuery)) and isinstance(event.from_user, User):
                tg_id = event.from_user.id

            if tg_id and self.session_maker:
                async with self.session_maker() as session:
                    repo = PostgresUserRepo(session)
                    user = await repo.get_by_tg_id(tg_id)
                    if user and user.language in ("ru", "en"):
                        lang = user.language
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
