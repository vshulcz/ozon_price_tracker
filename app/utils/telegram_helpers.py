from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import User


@dataclass
class TelegramUserData:
    tg_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    is_bot: bool
    is_premium: bool


def extract_user_data(user: User) -> TelegramUserData:
    return TelegramUserData(
        tg_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_bot=user.is_bot,
        is_premium=getattr(user, "is_premium", False),
    )
