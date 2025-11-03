from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.i18n import Lang
from app.db.models import User


@dataclass
class UserDTO:
    id: int
    tg_user_id: int
    language: Lang = "ru"


class PostgresUserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dto(u: User) -> UserDTO:
        return UserDTO(id=u.id, tg_user_id=u.tg_user_id, language=u.language)

    async def ensure_user(self, tg_user_id: int) -> UserDTO:
        res = await self.session.execute(select(User).where(User.tg_user_id == tg_user_id))
        u = res.scalar_one_or_none()
        if u:
            return self._to_dto(u)
        u = User(tg_user_id=tg_user_id)
        self.session.add(u)
        await self.session.commit()
        await self.session.refresh(u)
        return self._to_dto(u)

    async def _get_by_tg_id(self, tg_user_id: int) -> UserDTO | None:
        res = await self.session.execute(select(User).where(User.tg_user_id == tg_user_id))
        u = res.scalar_one_or_none()
        return self._to_dto(u) if u else None

    async def get_language(self, tg_user_id: int) -> Lang:
        user = await self.ensure_user(tg_user_id)
        return user.language

    async def set_language(self, tg_user_id: int, lang: Lang) -> None:
        await self.session.execute(
            update(User).where(User.tg_user_id == tg_user_id).values(language=lang)
        )
        await self.session.commit()

    async def get_by_id(self, user_id: int) -> UserDTO | None:
        res = await self.session.execute(select(User).where(User.id == user_id))
        u = res.scalar_one_or_none()
        return self._to_dto(u) if u else None
