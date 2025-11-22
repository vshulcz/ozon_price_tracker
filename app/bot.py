from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import Settings
from app.db.db import init_engine_and_schema
from app.db.migrations import run_migrations
from app.handlers import add_product as add_handlers
from app.handlers import products as products_handlers
from app.handlers import settings as settings_handlers
from app.handlers import start as start_handlers
from app.middlewares.db_session import DBSessionMiddleware
from app.middlewares.errors import ErrorsMiddleware
from app.scheduler import setup_scheduler
from app.services.ozon_client import shutdown_browser


async def setup_bot_commands(bot: Bot) -> None:
    cmds = [
        BotCommand(command="start", description="Start / Запуск"),
        BotCommand(command="menu", description="Main menu / Главное меню"),
    ]
    await bot.set_my_commands(cmds)


async def main() -> None:
    settings = Settings.from_env()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )

    logger = logging.getLogger(__name__)

    if settings.auto_migrate:
        logger.info("AUTO_MIGRATE is enabled, running database migrations...")
        try:
            run_migrations(settings.database_url)
        except Exception as e:
            logger.error("Failed to run migrations: %s", e)
            raise

    engine, session_maker = init_engine_and_schema(settings.database_url)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    errmw = ErrorsMiddleware(session_maker)
    dp.message.middleware(errmw)
    dp.callback_query.middleware(errmw)

    dbmw = DBSessionMiddleware(session_maker)
    dp.message.middleware(dbmw)
    dp.callback_query.middleware(dbmw)

    dp.include_router(start_handlers.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(add_handlers.router)
    dp.include_router(products_handlers.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await setup_bot_commands(bot)

    scheduler = setup_scheduler(bot, settings.price_check_hours, session_maker)

    logger.info("Bot started. Polling with scheduler...")
    try:
        await dp.start_polling(bot)
    finally:
        with suppress(Exception):
            scheduler.shutdown(wait=False)
        with suppress(Exception):
            await bot.session.close()
        with suppress(Exception):
            await shutdown_browser()
        with suppress(Exception):
            await engine.dispose()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
