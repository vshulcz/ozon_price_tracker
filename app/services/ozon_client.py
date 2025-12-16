from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import platform
import re
import shlex
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlparse, urlsplit, urlunsplit

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

FIRST_PARTY = ("ozon.ru", "ozone.ru", "cdn1.ozone.ru", "cdn2.ozone.ru", "ir.ozone.ru")
_WIDGET_PRICE_KEYS = ("webPrice", "webProductPrices", "webSale")
_WIDGET_TITLE_KEYS = ("webProductHeading",)

ALLOWED_RESOURCE_TYPES = {"document", "script", "xhr", "fetch", "other"}


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class OzonBlockedError(RuntimeError):
    """Raised when Ozon blocks access to product data."""

    pass


@dataclass
class OzonProductInfo:
    title: str
    price_no_card: Decimal | None
    price_with_card: Decimal | None

    @property
    def price_for_compare(self) -> Decimal | None:
        return self.price_with_card or self.price_no_card


def _to_www(u: str) -> str:
    s = urlsplit(u)
    host = s.netloc
    if host.startswith("ozon.ru"):
        host = "www.ozon.ru"
    elif host.endswith(".ozon.ru") and not host.startswith("www."):
        host = "www.ozon.ru"
    return urlunsplit((s.scheme or "https", host, s.path, s.query, s.fragment))


def _normalize_price(text: str) -> Decimal | None:
    if not text:
        return None

    cleaned = (
        text.replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u2009", " ")
        .replace(" ", "")
        .replace(",", ".")
        .replace("₽", "")
    )
    m = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if not m:
        return None
    try:
        return Decimal(m.group(1))
    except Exception:
        return None


class _Browser:
    _pl = None
    _browser: Browser | None = None
    _ctx: BrowserContext | None = None
    _lock = asyncio.Lock()
    _headless = _env_bool("OZON_HEADLESS", True)
    _skip_challenge = _env_bool("OZON_SKIP_CHALLENGE", False)
    _channel_override = os.getenv("OZON_BROWSER_CHANNEL")
    _extra_args = shlex.split(os.getenv("OZON_BROWSER_ARGS", ""))

    @classmethod
    async def ensure_started(cls) -> None:
        if cls._browser:
            return

        async with cls._lock:
            if cls._browser:
                return

            logger.info("Starting browser for Ozon scraping...")
            prof = _os_profile()
            cls._pl = await async_playwright().start()

            args = prof["args"] + [
                "--disable-blink-features=AutomationControlled",
            ]
            if cls._extra_args:
                args.extend(cls._extra_args)

            launch_kwargs = {
                "headless": cls._headless,
                "args": args,
                "ignore_default_args": ["--enable-automation"],
                "timeout": 300000,
            }
            channel = cls._channel_override
            if channel == "":
                channel = None
            if channel is None:
                channel = prof["channel"]
            if channel:
                try:
                    launch_kwargs["channel"] = channel
                    cls._browser = await cls._pl.chromium.launch(**launch_kwargs)
                    logger.info("Browser started with channel: %s", channel)
                except Exception as e:
                    logger.warning("Failed to start browser with channel, using default: %s", e)
                    launch_kwargs.pop("channel", None)
                    cls._browser = await cls._pl.chromium.launch(**launch_kwargs)
            else:
                cls._browser = await cls._pl.chromium.launch(**launch_kwargs)
                logger.info("Browser started without channel")

            storage_state = None
            storage_path = _cookie_storage_path()
            if storage_path.exists():
                storage_state = storage_path.as_posix()
                logger.info("Loading Ozon cookies from %s", storage_path)

            context_kwargs = {
                "locale": "ru-RU",
                "user_agent": prof["ua"],
                "viewport": {"width": 1366, "height": 768},
                "java_script_enabled": True,
                "color_scheme": "light",
                "service_workers": "block",
                "extra_http_headers": {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            }
            if storage_state:
                context_kwargs["storage_state"] = storage_state

            cls._ctx = await cls._browser.new_context(**context_kwargs)
            await cls._ctx.add_init_script(f"""
                Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
                try {{
                  Object.defineProperty(navigator, 'platform',
                                           {{ get: () => '{prof["platform_js"]}' }});
                }} catch (e) {{}}
            """)
            await cls._ctx.route("**/*", _route_blocker)

    @classmethod
    async def page(cls) -> Page:
        await cls.ensure_started()
        assert cls._ctx is not None
        page = await cls._ctx.new_page()
        return page

    @classmethod
    async def shutdown(cls) -> None:
        logger.info("Shutting down browser...")
        async with cls._lock:
            with contextlib.suppress(Exception):
                if cls._ctx:
                    await cls._ctx.close()
                cls._ctx = None
            with contextlib.suppress(Exception):
                if cls._browser:
                    await cls._browser.close()
                cls._browser = None
            with contextlib.suppress(Exception):
                if cls._pl:
                    await cls._pl.stop()
                cls._pl = None
        logger.info("Browser shutdown completed")


async def _route_blocker(route, request):
    host = (urlparse(request.url).hostname or "").lower()
    if any(host.endswith(d) for d in FIRST_PARTY):
        return await route.continue_()
    if request.resource_type in {"media"}:
        return await route.abort()
    return await route.continue_()


async def _pass_ozon_challenge(ctx: BrowserContext, page: Page, timeout_ms=60000) -> bool:
    if _Browser._skip_challenge:
        return True
    logger.debug("Passing Ozon anti-bot challenge...")
    try:
        await page.goto(
            "https://www.ozon.ru/?abt_att=1&__rr=1",
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
    except Exception as e:
        logger.warning("Failed to navigate to Ozon challenge page: %s", e)
        return False

    try:
        async with page.expect_response(
            lambda r: ("www.ozon.ru/abt/result" in r.url) and r.status == 200,
            timeout=timeout_ms,
        ) as resp_info:
            await resp_info.value
    except Exception as e:
        logger.warning("Failed to pass Ozon challenge: %s", e)
        return False

    cookies = await ctx.cookies("https://www.ozon.ru/")
    ok = any(c.get("name") == "abt_data" for c in cookies)
    logger.debug("Ozon challenge result: %s", "passed" if ok else "failed")
    return ok


async def _warmup_challenge(ctx: BrowserContext) -> bool:
    if _Browser._skip_challenge:
        return True
    page = None
    passed = False
    try:
        page = await ctx.new_page()
        passed = await _pass_ozon_challenge(ctx, page, timeout_ms=30000)
        if passed:
            await _save_storage_state(ctx)
    except Exception as exc:
        logger.debug("Warmup challenge failed: %s", exc)
    finally:
        if page:
            with contextlib.suppress(Exception):
                await page.close()
    return passed


async def fetch_product_info(url: str, *, retries: int = 2) -> OzonProductInfo:
    if not re.search(r"^https?://(www\.)?ozon\.[^/]+/", url, re.IGNORECASE):
        logger.warning("Invalid Ozon URL: %s", url[:100])
        raise ValueError("Not an Ozon product URL")

    url = _to_www(url)
    logger.debug("Fetching product info from: %s", url[:100])

    for attempt in range(retries + 1):
        try:
            result = await fetch_product_info_via_api(url)
            logger.info(
                "Product fetched | URL: %s | Title: %s | Price card: %s | Price: %s",
                url[:100],
                result.title[:50],
                result.price_with_card,
                result.price_no_card,
            )
            return result
        except Exception as e:
            logger.warning(
                "Fetch attempt %d/%d failed for URL %s: %s",
                attempt + 1,
                retries + 1,
                url[:100],
                e,
            )
            if attempt < retries:
                await asyncio.sleep(1.2)
    logger.error("All fetch attempts failed for URL: %s", url[:100])
    raise OzonBlockedError()


async def shutdown_browser() -> None:
    await _Browser.shutdown()


def _os_profile():
    sysname = platform.system()
    if sysname == "Linux":
        return {
            "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "platform_js": "Linux x86_64",
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--lang=ru-RU",
            ],
            "channel": None,
        }
    elif sysname == "Darwin":
        return {
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "platform_js": "MacIntel",
            "args": ["--lang=ru-RU"],
            "channel": "chrome",
        }
    else:  # Windows
        return {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "platform_js": "Win32",
            "args": ["--lang=ru-RU"],
            "channel": "chrome",
        }


def _iter_widget_objs(widget_states: dict[str, str]):
    for k, v in (widget_states or {}).items():
        if not isinstance(v, str):
            continue
        with contextlib.suppress(Exception):
            yield k, json.loads(v)


def _is_price_widget(key: str) -> bool:
    low = key.lower()
    return any(name.lower() in low for name in _WIDGET_PRICE_KEYS)


def _is_title_widget(key: str) -> bool:
    low = key.lower()
    return any(name.lower() in low for name in _WIDGET_TITLE_KEYS)


def _pick_title(data: dict) -> str | None:
    for k, obj in _iter_widget_objs(data.get("widgetStates") or {}):
        if _is_title_widget(k):
            t = obj.get("title")
            if isinstance(t, str) and t.strip():
                return t.strip()
    with contextlib.suppress(Exception):
        t = (data.get("seo") or {}).get("title")
        if t and isinstance(t, str) and t.strip():
            return t.strip()
    for _, obj in _iter_widget_objs(data.get("widgetStates") or {}):
        with contextlib.suppress(Exception):
            t = (obj.get("cellTrackingInfo") or {}).get("product", {}).get("title") or (
                obj.get("product") or {}
            ).get("title")
            if t and isinstance(t, str) and t.strip():
                return t.strip()
    return None


def _pick_prices(data: dict) -> tuple[Decimal | None, Decimal | None]:
    with_card = None
    no_card = None

    for k, obj in _iter_widget_objs(data.get("widgetStates") or {}):
        if not _is_price_widget(k):
            continue

        is_avail = obj.get("isAvailable", True)

        cand_card = obj.get("cardPrice")
        cand_no = obj.get("price")
        if cand_card is None and cand_no is None:
            product = (obj.get("cellTrackingInfo") or {}).get("product", {}) or obj.get(
                "product", {}
            )
            cand_card = cand_card or product.get("cardPrice") or product.get("finalPrice")
            cand_no = cand_no or product.get("price") or product.get("originalPrice")

        wc = (
            _normalize_price(str(cand_card))
            if isinstance(cand_card, str)
            else (_normalize_price(str(cand_card)) if cand_card is not None else None)
        )
        nc = (
            _normalize_price(str(cand_no))
            if isinstance(cand_no, str)
            else (_normalize_price(str(cand_no)) if cand_no is not None else None)
        )

        if wc and (not with_card or is_avail):
            with_card = wc
        if nc and (not no_card or is_avail):
            no_card = nc

        if with_card and no_card:
            break

    if not (with_card and no_card):
        dump = json.dumps(data, ensure_ascii=False)
        prices = [
            _normalize_price(m) for m in re.findall(r"(\d[\d\s\u00A0\u2009\u202F]*)\s*₽", dump)
        ]
        prices = [p for p in prices if p]
        if prices:
            if not with_card and len(prices) >= 1:
                with_card = prices[0]
            if not no_card and len(prices) >= 2:
                no_card = prices[1]

    return with_card, no_card


async def fetch_product_info_via_api(url: str) -> OzonProductInfo:
    normalized_url = _to_www(url)
    ctx = await _ensure_browser_context()
    if not ctx:
        logger.error("Browser context unavailable for URL: %s", url[:100])
        raise OzonBlockedError("ozon_browser_unavailable")

    data = await _fetch_with_composer(ctx, normalized_url)
    if not data:
        logger.info("Composer empty for %s, forcing challenge refresh", url[:80])
        refreshed = await _warmup_challenge(ctx)
        if refreshed:
            data = await _fetch_with_composer(ctx, normalized_url)
        if not data:
            logger.error("Composer API returned empty payload for URL: %s", url[:100])
            raise OzonBlockedError("ozon_composer_empty")

    title = _pick_title(data)
    if not title:
        logger.warning("Could not extract title from Ozon API for URL: %s", url[:100])
        title = "Ozon item"

    with_card, no_card = _pick_prices(data)

    if not with_card and not no_card:
        logger.warning(
            "Could not extract any prices from Ozon API for URL: %s | Title: %s",
            url[:100],
            title[:50],
        )

    return OzonProductInfo(title=title, price_with_card=with_card, price_no_card=no_card)


async def _fetch_with_composer(ctx: BrowserContext, url: str, attempts: int = 3) -> dict | None:
    relative = _relative_url_path(url)
    q = quote(relative, safe="/:?=&%")
    api_url = f"https://www.ozon.ru/api/composer-api.bx/page/json/v2?url={q}"
    headers = {
        "Accept": "application/json",
        "Referer": "https://www.ozon.ru/",
        "X-O3-App-Name": "dweb_client",
        "X-O3-App-Version": "1.0.0",
    }

    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            resp = await ctx.request.get(api_url, headers=headers)
        except Exception as exc:
            logger.warning("Composer request failed (%s/%s): %s", attempt, attempts, exc)
            resp = None

        if resp and getattr(resp, "ok", False):
            with contextlib.suppress(Exception):
                data = await resp.json()
                if data:
                    logger.debug("Composer API succeeded on attempt %s", attempt)
                    return data

        status = getattr(resp, "status", None) if resp else None
        retry_after = 0.0
        if resp and hasattr(resp, "headers"):
            with contextlib.suppress(Exception):
                retry_after = float(resp.headers.get("Retry-After", 0) or 0)

        if attempt < attempts:
            sleep_for = retry_after or delay
            logger.debug(
                "Composer API retry %s/%s in %.1fs (status=%s)",
                attempt,
                attempts,
                sleep_for,
                status,
            )
            await asyncio.sleep(sleep_for)
            delay = min(delay * 2, 10.0)

    return None


def _relative_url_path(url: str) -> str:
    parts = urlsplit(url)
    path_q = parts.path or "/"
    if parts.query:
        path_q = f"{path_q}?{parts.query}"
    return path_q


async def _ensure_browser_context() -> BrowserContext | None:
    try:
        await _Browser.ensure_started()
    except Exception as exc:
        logger.warning("Browser startup failed, reason: %s", exc)
        return None
    return _Browser._ctx


def _cookie_storage_path() -> Path:
    custom = os.getenv("OZON_COOKIE_PATH")
    return Path(custom) if custom else Path(".ozon_cookies.json")


async def _save_storage_state(ctx: BrowserContext) -> None:
    path = _cookie_storage_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        await ctx.storage_state(path=path.as_posix())
        logger.debug("Persisted Ozon cookies to %s", path)
    except Exception as exc:
        logger.warning("Failed to persist Ozon cookies to %s: %s", path, exc)
