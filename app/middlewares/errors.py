from __future__ import annotations

import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram.types import CallbackQuery, Message
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
        except Exception as e:
            user_id = None
            username = None
            event_type = type(event).__name__

            with contextlib.suppress(Exception):
                fu = getattr(event, "from_user", None)
                if fu:
                    user_id = getattr(fu, "id", None)
                    username = getattr(fu, "username", None)

            logger.exception(
                "Unhandled error | Event: %s | User ID: %s | Username: %s | Error: %s",
                event_type,
                user_id or "unknown",
                username or "unknown",
                e,
            )

        lang: Lang = "ru"

        tg_id = None
        with contextlib.suppress(Exception):
            fu = getattr(event, "from_user", None)
            tg_id = getattr(fu, "id", None)

        if tg_id and self.session_maker:
            try:
                async with self.session_maker() as session:
                    user_repo = PostgresUserRepo(session)
                    user = await user_repo.get_by_tg_id(tg_id)
                    if user and user.language in ("ru", "en"):
                        lang = user.language
            except Exception as e:
                logger.warning(
                    "Failed to determine user language for user %s: %s",
                    tg_id,
                    e,
                )

        text = i18n.t(lang, "error.unexpected")
        try:
            if isinstance(event, CallbackQuery):
                await event.answer("Error", show_alert=False)

                if isinstance(event.message, Message):
                    await event.message.answer(text)

            elif isinstance(event, Message):
                await event.answer(text)
        except Exception as e:
            logger.error(
                "Failed to send error message to user %s: %s",
                tg_id or "unknown",
                e,
            )

        return None
