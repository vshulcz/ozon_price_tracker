from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.products import ProductsRepo
from app.repositories.users import PostgresUserRepo


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
            try:
                return await handler(event, data)
            except Exception:
                with contextlib.suppress(Exception):
                    await session.rollback()
                raise
