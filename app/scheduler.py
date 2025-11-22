from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.i18n import Lang, i18n
from app.keyboards.products import deal_reached_kb
from app.repositories.products import ProductsRepo
from app.repositories.users import PostgresUserRepo
from app.services.ozon_client import fetch_product_info
from app.utils.logging import log_notification_sent, log_price_check, log_scheduler_event

logger = logging.getLogger(__name__)


async def _notify_deal_reached(
    bot: Bot,
    *,
    user_tg_id: int,
    lang: Lang,
    product_id: int,
    title: str,
    url: str,
    current: float,
    target: float,
) -> None:
    text = i18n.t(
        lang,
        "notif.deal_reached",
        title=title,
        current=f"{current:.2f}",
        target=f"{target:.2f}",
    )
    log_notification_sent(user_tg_id, product_id, "deal_reached")
    await bot.send_message(
        user_tg_id,
        text,
        reply_markup=deal_reached_kb(i18n, lang, product_id=product_id, url=url),
    )


async def _notify_deal_over(
    bot: Bot,
    *,
    user_tg_id: int,
    lang: Lang,
    product_id: int,
    title: str,
    current: float,
    target: float,
) -> None:
    text = i18n.t(
        lang,
        "notif.deal_over",
        title=title,
        current=f"{current:.2f}",
        target=f"{target:.2f}",
    )
    log_notification_sent(user_tg_id, product_id, "deal_over")
    await bot.send_message(user_tg_id, text, disable_web_page_preview=True)


async def refresh_prices_and_notify(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    log_scheduler_event("price_check_started")

    products_checked = 0
    notifications_sent = 0
    errors_count = 0

    async with session_maker() as session:
        users = PostgresUserRepo(session)
        products = ProductsRepo(session)

        async for p in products.list_all_active():
            try:
                info = await fetch_product_info(p.url)
                chosen = info.price_for_compare
                if chosen is None:
                    continue

                old_price = float(p.current_price) if p.current_price else None
                current = float(chosen)

                await products.update_current_and_history(p.id, current, source="scheduler")
                products_checked += 1

                user = await users.get_by_id(p.user_id)
                if not user:
                    continue

                target = float(p.target_price)
                prev_state = p.last_state

                log_price_check(
                    product_id=p.id,
                    title=p.title,
                    old_price=old_price,
                    new_price=current,
                    target_price=target,
                )

                if current <= target:
                    if prev_state != "below":
                        await _notify_deal_reached(
                            bot,
                            user_tg_id=user.tg_user_id,
                            lang=user.language,
                            product_id=p.id,
                            title=p.title,
                            url=p.url,
                            current=current,
                            target=target,
                        )
                        await products.set_last_state(p.id, "below", last_notified_price=current)
                        notifications_sent += 1
                else:
                    if prev_state == "below":
                        await _notify_deal_over(
                            bot,
                            user_tg_id=user.tg_user_id,
                            lang=user.language,
                            product_id=p.id,
                            title=p.title,
                            current=current,
                            target=target,
                        )
                        await products.set_last_state(p.id, "above", last_notified_price=None)
                        notifications_sent += 1
            except Exception as e:
                errors_count += 1
                logger.exception("Failed to refresh product %s: %s", p.id, e)

    log_scheduler_event(
        "price_check_completed",
        products_checked=products_checked,
        notifications_sent=notifications_sent,
        errors=errors_count,
    )


def setup_scheduler(
    bot: Bot, cron_trigger: str, session_maker: async_sessionmaker[AsyncSession]
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        refresh_prices_and_notify,
        CronTrigger(hour=cron_trigger, minute=0),
        kwargs={"bot": bot, "session_maker": session_maker},
    )
    scheduler.start()
    log_scheduler_event("scheduler_started", cron=cron_trigger)
    logger.info("Scheduler configured with hours: %s", cron_trigger)
    return scheduler
