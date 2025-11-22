from __future__ import annotations

import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.products import ProductsRepo
from app.repositories.users import PostgresUserRepo
from app.utils.telegram_helpers import extract_user_data

logger = logging.getLogger(__name__)


class DBSessionMiddleware:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self.session_maker = session_maker

    async def __call__(
        self,
        handler: Callable[[Any, Any], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_maker() as session:
            data["db_session"] = session
            data["user_repo"] = PostgresUserRepo(session)
            data["products"] = ProductsRepo(session)

            user_repo = data["user_repo"]
            from_user = getattr(event, "from_user", None)
            if from_user:
                try:
                    user_data = extract_user_data(from_user)
                    await user_repo.ensure_user(
                        tg_user_id=user_data.tg_user_id,
                        username=user_data.username,
                        first_name=user_data.first_name,
                        last_name=user_data.last_name,
                        is_bot=user_data.is_bot,
                        is_premium=user_data.is_premium,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to update user data | User ID: %s | Error: %s",
                        from_user.id,
                        e,
                    )

            try:
                return await handler(event, data)
            except Exception:
                with contextlib.suppress(Exception):
                    await session.rollback()
                raise
