from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    log_level: str = "INFO"
    price_check_hours: str = "9,15,21"
    auto_migrate: bool = True

    @staticmethod
    def from_env() -> Settings:
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise RuntimeError("BOT_TOKEN is not set. Provide it via env or .env file.")

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError(
                "DATABASE_URL is not set (e.g. postgres://user:pass@host:5432/dbname)"
            )

        auto_migrate = os.getenv("AUTO_MIGRATE", "true").lower() in ("true", "1", "yes")

        return Settings(
            bot_token=token,
            database_url=db_url,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            price_check_hours=os.getenv("PRICE_CHECK_HOURS", "9,15,21"),
            auto_migrate=auto_migrate,
        )
