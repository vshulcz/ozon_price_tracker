from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth

logger = logging.getLogger(__name__)


class OzonBlockedError(RuntimeError):
    pass


@dataclass
class ProductInfo:
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


class _SeleniumBrowser:
    _driver: webdriver.Chrome | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def ensure_started(cls) -> None:
        if cls._driver:
            return

        async with cls._lock:
            if cls._driver:
                return

            logger.info("Starting Chrome browser for Ozon scraping...")

            options = Options()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")
            options.add_argument("--headless=new")
            options.add_argument("--lang=ru-RU")

            options.add_argument("--disable-images")
            options.page_load_strategy = "eager"

            options.add_argument(
                "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )

            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            cls._driver = webdriver.Chrome(options=options)

            stealth(
                cls._driver,
                languages=["ru-RU", "ru", "en-US", "en"],
                vendor="Google Inc.",
                platform="Linux x86_64",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )

            logger.info("Chrome browser started successfully with stealth mode")

    @classmethod
    def get_driver(cls) -> webdriver.Chrome:
        if not cls._driver:
            raise RuntimeError("Browser not started. Call ensure_started() first.")
        return cls._driver

    @classmethod
    async def shutdown(cls) -> None:
        logger.info("Shutting down browser...")
        async with cls._lock:
            if cls._driver:
                with contextlib.suppress(Exception):
                    cls._driver.quit()
                cls._driver = None
        logger.info("Browser shutdown completed")


async def fetch_product_info(url: str, *, retries: int = 2) -> ProductInfo:
    if not re.search(r"^https?://(www\.)?ozon\.[^/]+/", url, re.IGNORECASE):
        logger.warning("Invalid Ozon URL: %s", url[:100])
        raise ValueError("Not an Ozon product URL")

    url = _to_www(url)
    logger.debug("Fetching product info from: %s", url[:100])

    for attempt in range(retries + 1):
        try:
            await _SeleniumBrowser.ensure_started()
            driver = _SeleniumBrowser.get_driver()

            await asyncio.to_thread(driver.get, url)
            logger.debug("Page loaded: %s", url[:100])

            wait = WebDriverWait(driver, 5)

            try:
                title_element = wait.until(
                    ec.presence_of_element_located(
                        (By.XPATH, "//div[@data-widget='webProductHeading']//h1")
                    )
                )
                title = title_element.text.strip()
                logger.info("Found title: %s", title[:50])
            except Exception as e:
                logger.error("Failed to extract title: %s", e)
                title = "Ozon item"

            price_with_card = None
            try:
                price_card_element = driver.find_element(
                    By.XPATH, "//span[@class='tsHeadline600Large']"
                )
                price_text = price_card_element.text.strip()
                price_with_card = _normalize_price(price_text)
                logger.info("Found price with card: %s", price_with_card)
            except Exception as e:
                logger.warning("Failed to extract price with card: %s", e)

            price_no_card = None
            try:
                price_no_card_element = driver.find_element(
                    By.XPATH,
                    "//span[contains(text(),'₽') and contains(@class,'tsHeadline500Medium')]",
                )
                price_text = price_no_card_element.text.strip()
                price_no_card = _normalize_price(price_text)
                logger.info("Found price without card: %s", price_no_card)
            except Exception as e:
                logger.warning("Failed to extract price without card: %s", e)

            if not price_with_card and not price_no_card:
                logger.warning("Could not extract any prices from: %s", url[:100])

            result = ProductInfo(
                title=title, price_with_card=price_with_card, price_no_card=price_no_card
            )

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
                await asyncio.sleep(2)

    logger.error("All fetch attempts failed for URL: %s", url[:100])
    raise OzonBlockedError()


async def shutdown_browser() -> None:
    await _SeleniumBrowser.shutdown()
