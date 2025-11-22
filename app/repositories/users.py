from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.i18n import Lang


@dataclass
class UserDTO:
    id: int
    tg_user_id: int
    language: Lang = "ru"
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_bot: bool = False
    is_premium: bool = False
    last_active_at: datetime | None = None
    total_interactions: int = 0
    notifications_enabled: bool = True
    timezone: str | None = None


class PostgresUserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dto(u: User) -> UserDTO:
        return UserDTO(
            id=u.id,
            tg_user_id=u.tg_user_id,
            language=u.language,
            username=u.username,
            first_name=u.first_name,
            last_name=u.last_name,
            is_bot=u.is_bot,
            is_premium=u.is_premium,
            last_active_at=u.last_active_at,
            total_interactions=u.total_interactions,
            notifications_enabled=u.notifications_enabled,
            timezone=u.timezone,
        )

    async def ensure_user(
        self,
        tg_user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_bot: bool = False,
        is_premium: bool = False,
    ) -> UserDTO:
        """Ensure user exists in DB. Create if new, update fields if existing."""
        res = await self.session.execute(select(User).where(User.tg_user_id == tg_user_id))
        u = res.scalar_one_or_none()
        now = datetime.now()

        if u:
            u.username = username
            u.first_name = first_name
            u.last_name = last_name
            u.is_bot = is_bot
            u.is_premium = is_premium
            u.last_active_at = now
            u.total_interactions += 1
            u.updated_at = now
            await self.session.commit()
            await self.session.refresh(u)
            return self._to_dto(u)

        u = User(
            tg_user_id=tg_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_bot=is_bot,
            is_premium=is_premium,
            last_active_at=now,
            total_interactions=1,
        )
        self.session.add(u)
        await self.session.commit()
        await self.session.refresh(u)
        return self._to_dto(u)

    async def get_by_tg_id(self, tg_user_id: int) -> UserDTO | None:
        res = await self.session.execute(select(User).where(User.tg_user_id == tg_user_id))
        u = res.scalar_one_or_none()
        return self._to_dto(u) if u else None

    async def get_language(self, tg_user_id: int) -> Lang:
        user = await self.ensure_user(tg_user_id)
        return user.language

    async def set_language(self, tg_user_id: int, lang: Lang) -> None:
        await self.session.execute(
            update(User)
            .where(User.tg_user_id == tg_user_id)
            .values(language=lang, updated_at=func.now())
        )
        await self.session.commit()

    async def update_activity(self, tg_user_id: int) -> None:
        await self.session.execute(
            update(User)
            .where(User.tg_user_id == tg_user_id)
            .values(
                last_active_at=func.now(),
                total_interactions=User.total_interactions + 1,
                updated_at=func.now(),
            )
        )
        await self.session.commit()

    async def set_notifications(self, tg_user_id: int, enabled: bool) -> None:
        await self.session.execute(
            update(User)
            .where(User.tg_user_id == tg_user_id)
            .values(notifications_enabled=enabled, updated_at=func.now())
        )
        await self.session.commit()

    async def set_timezone(self, tg_user_id: int, timezone: str) -> None:
        await self.session.execute(
            update(User)
            .where(User.tg_user_id == tg_user_id)
            .values(timezone=timezone, updated_at=func.now())
        )
        await self.session.commit()

    async def get_by_id(self, user_id: int) -> UserDTO | None:
        res = await self.session.execute(select(User).where(User.id == user_id))
        u = res.scalar_one_or_none()
        return self._to_dto(u) if u else None
