from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery, Message, User

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _format_user(user: User) -> str:
    username = f"@{user.username}" if getattr(user, "username", None) else "no_username"
    full_name = getattr(user, "full_name", None) or "Unknown"
    user_id = getattr(user, "id", "unknown")
    return f"{full_name} ({username}, id={user_id})"


def log_user_action(action: str, **extra: Any) -> None:
    logger.info(
        "User action: %s | Extra: %s",
        action,
        " | ".join(f"{k}={v}" for k, v in extra.items()) if extra else "none",
    )


def log_message_handler(action_name: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(message: Message, *args: Any, **kwargs: Any) -> Any:
            from_user = message.from_user
            if from_user:
                logger.info(
                    "Message handler: %s | User: %s | Text: %s",
                    action_name,
                    _format_user(from_user),
                    (message.text or "")[:100],
                )
            return await func(message, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def log_callback_handler(action_name: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(cb: CallbackQuery, *args: Any, **kwargs: Any) -> Any:
            from_user = cb.from_user
            callback_data = getattr(cb, "data", "no_data")
            logger.info(
                "Callback handler: %s | User: %s | Data: %s",
                action_name,
                _format_user(from_user),
                callback_data,
            )
            return await func(cb, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def log_product_action(
    user_id: int, action: str, product_id: int | None = None, **extra: Any
) -> None:
    details = {"user_id": user_id, "action": action}
    if product_id is not None:
        details["product_id"] = product_id
    details.update(extra)

    logger.info(
        "Product action: %s | %s",
        action,
        " | ".join(f"{k}={v}" for k, v in details.items()),
    )


def log_price_check(
    product_id: int,
    title: str,
    old_price: float | None,
    new_price: float | None,
    target_price: float | None,
) -> None:
    price_change = ""
    if old_price is not None and new_price is not None:
        diff = new_price - old_price
        price_change = f"({diff:+.2f})"

    logger.info(
        "Price check | Product ID: %d | Title: %s | Old: %s | New: %s %s | Target: %s",
        product_id,
        title[:50],
        f"{old_price:.2f}" if old_price else "—",
        f"{new_price:.2f}" if new_price else "—",
        price_change,
        f"{target_price:.2f}" if target_price else "—",
    )


def log_notification_sent(user_id: int, product_id: int, notification_type: str) -> None:
    logger.info(
        "Notification sent | User ID: %d | Product ID: %d | Type: %s",
        user_id,
        product_id,
        notification_type,
    )


def log_error(context: str, error: Exception, **extra: Any) -> None:
    logger.error(
        "Error in %s: %s | %s",
        context,
        error,
        " | ".join(f"{k}={v}" for k, v in extra.items()) if extra else "no extra info",
        exc_info=True,
    )


def log_scheduler_event(event: str, **extra: Any) -> None:
    logger.info(
        "Scheduler: %s | %s",
        event,
        " | ".join(f"{k}={v}" for k, v in extra.items()) if extra else "no details",
    )
