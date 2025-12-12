from __future__ import annotations

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Core bot metrics
bot_updates_total = Counter(
    "bot_updates_total",
    "Number of Telegram updates processed by type",
    labelnames=("update_type",),
)

bot_errors_total = Counter(
    "bot_errors_total",
    "Number of errors raised while processing updates",
    labelnames=("source",),
)

notifications_sent_total = Counter(
    "notifications_sent_total",
    "Number of notifications delivered to users",
    labelnames=("kind",),
)

# Scheduler / scraping metrics
price_check_duration_seconds = Histogram(
    "price_check_duration_seconds",
    "Duration of the full price refresh cycle",
)

total_products_checked = Counter(
    "products_checked_total",
    "Total number of products whose price was refreshed",
)

total_price_check_errors = Counter(
    "price_check_errors_total",
    "Total number of errors encountered during price refresh",
)

scheduler_runs_total = Counter(
    "scheduler_runs_total",
    "Number of scheduler executions",
    labelnames=("status",),
)

inflight_products_gauge = Gauge(
    "products_refresh_inflight",
    "Number of products currently being processed",
)

# External marketplace scraping
marketplace_request_duration_seconds = Histogram(
    "marketplace_request_duration_seconds",
    "Duration of marketplace scraping calls",
    labelnames=("marketplace", "result"),
)

marketplace_requests_total = Counter(
    "marketplace_requests_total",
    "Number of marketplace scraping attempts",
    labelnames=("marketplace", "result"),
)

marketplace_blocked_total = Counter(
    "marketplace_blocked_total",
    "Number of times marketplace blocked the scraper",
    labelnames=("marketplace",),
)


_runner: web.AppRunner | None = None


async def _metrics_handler(_: web.Request) -> web.Response:
    payload = generate_latest()
    return web.Response(body=payload, content_type=CONTENT_TYPE_LATEST)


async def start_metrics_server(host: str, port: int) -> None:
    global _runner  # noqa: PLW0603
    if _runner is not None:
        return

    app = web.Application()
    app.router.add_get("/metrics", _metrics_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    _runner = runner


async def stop_metrics_server() -> None:
    global _runner  # noqa: PLW0603
    if _runner is None:
        return

    await _runner.cleanup()
    _runner = None
