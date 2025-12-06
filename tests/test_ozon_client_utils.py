from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ozon_client import (
    OzonBlockedError,
    ProductInfo,
    _normalize_price,
    _SeleniumBrowser,
    _to_www,
    fetch_product_info,
    shutdown_browser,
)


def test_normalize_price():
    vals = [
        _normalize_price("1 999,90 ₽"),
        _normalize_price("1 999.90 руб"),  # noqa: RUF001
        _normalize_price("1999.90"),
        _normalize_price("  1 999,90"),
    ]
    assert all(v == Decimal("1999.90") for v in vals)


def test_normalize_price_with_various_formats():
    assert _normalize_price("1\u00a0999,90\u202f₽") == Decimal("1999.90")
    assert _normalize_price("999₽") == Decimal("999")
    assert _normalize_price("1 234 567,89") == Decimal("1234567.89")
    assert _normalize_price("") is None
    assert _normalize_price("no numbers") is None
    assert _normalize_price("abc₽xyz") is None


def test_to_www_normalizes_host():
    assert _to_www("https://ozon.ru/item/42").startswith("https://www.ozon.ru/")
    assert _to_www("https://sub.ozon.ru/item/42").startswith("https://www.ozon.ru/")
    assert _to_www("http://www.ozon.ru/item/42").startswith("http://www.ozon.ru/")


def test_to_www_preserves_path_and_query():
    url = _to_www("https://ozon.ru/product/item-123?q=test")
    assert "www.ozon.ru" in url
    assert "/product/item-123" in url
    assert "q=test" in url


def test_to_www_with_different_subdomains():
    url1 = _to_www("https://m.ozon.ru/item/42")
    assert "www.ozon.ru" in url1

    url2 = _to_www("https://api.ozon.ru/item/42")
    assert "www.ozon.ru" in url2


def test_product_info_price_for_compare():
    info1 = ProductInfo(title="Test", price_with_card=Decimal("100"), price_no_card=Decimal("150"))
    assert info1.price_for_compare == Decimal("100")

    info2 = ProductInfo(title="Test", price_with_card=None, price_no_card=Decimal("150"))
    assert info2.price_for_compare == Decimal("150")

    info3 = ProductInfo(title="Test", price_with_card=Decimal("100"), price_no_card=None)
    assert info3.price_for_compare == Decimal("100")

    info4 = ProductInfo(title="Test", price_with_card=None, price_no_card=None)
    assert info4.price_for_compare is None


@pytest.mark.asyncio
async def test_selenium_browser_ensure_started():
    _SeleniumBrowser._driver = None

    with (
        patch("app.services.ozon_client.webdriver.Chrome") as mock_chrome,
        patch("app.services.ozon_client.stealth"),
    ):
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        await _SeleniumBrowser.ensure_started()

        assert _SeleniumBrowser._driver is mock_driver
        assert mock_chrome.called

        mock_chrome.reset_mock()
        await _SeleniumBrowser.ensure_started()
        assert not mock_chrome.called


@pytest.mark.asyncio
async def test_selenium_browser_get_driver_without_start():
    _SeleniumBrowser._driver = None

    with pytest.raises(RuntimeError, match="Browser not started"):
        _SeleniumBrowser.get_driver()


@pytest.mark.asyncio
async def test_selenium_browser_shutdown():
    mock_driver = MagicMock()
    _SeleniumBrowser._driver = mock_driver

    await _SeleniumBrowser.shutdown()

    assert mock_driver.quit.called
    assert _SeleniumBrowser._driver is None


@pytest.mark.asyncio
async def test_selenium_browser_shutdown_handles_exceptions():
    mock_driver = MagicMock()
    mock_driver.quit.side_effect = Exception("Quit failed")
    _SeleniumBrowser._driver = mock_driver

    await _SeleniumBrowser.shutdown()
    assert _SeleniumBrowser._driver is None


@pytest.mark.asyncio
async def test_fetch_product_info_invalid_url():
    with pytest.raises(ValueError, match="Not an Ozon product URL"):
        await fetch_product_info("https://example.com/product")

    with pytest.raises(ValueError, match="Not an Ozon product URL"):
        await fetch_product_info("https://amazon.com/item")


@pytest.mark.asyncio
async def test_fetch_product_info_success():
    mock_driver = MagicMock()
    mock_title_element = MagicMock()
    mock_title_element.text = "Test Product Title"
    mock_price_card_element = MagicMock()
    mock_price_card_element.text = "1 999,90 ₽"
    mock_price_no_card_element = MagicMock()
    mock_price_no_card_element.text = "2 499,00 ₽"

    mock_wait = MagicMock()
    mock_wait.until.return_value = mock_title_element

    def mock_find_element(by, xpath):
        if "tsHeadline600Large" in xpath:
            return mock_price_card_element
        return mock_price_no_card_element

    mock_driver.find_element = mock_find_element

    with (
        patch.object(_SeleniumBrowser, "ensure_started", new_callable=AsyncMock),
        patch.object(_SeleniumBrowser, "get_driver", return_value=mock_driver),
        patch("app.services.ozon_client.asyncio.to_thread", new_callable=AsyncMock),
        patch("app.services.ozon_client.WebDriverWait", return_value=mock_wait),
    ):
        result = await fetch_product_info("https://ozon.ru/product/test-123")

        assert result.title == "Test Product Title"
        assert result.price_with_card == Decimal("1999.90")
        assert result.price_no_card == Decimal("2499.00")


@pytest.mark.asyncio
async def test_fetch_product_info_no_prices():
    mock_driver = MagicMock()
    mock_title_element = MagicMock()
    mock_title_element.text = "Test Product"

    mock_wait = MagicMock()
    mock_wait.until.return_value = mock_title_element

    def mock_find_element(by, xpath):
        from selenium.common.exceptions import NoSuchElementException

        raise NoSuchElementException("Element not found")

    mock_driver.find_element = mock_find_element

    with (
        patch.object(_SeleniumBrowser, "ensure_started", new_callable=AsyncMock),
        patch.object(_SeleniumBrowser, "get_driver", return_value=mock_driver),
        patch("app.services.ozon_client.asyncio.to_thread", new_callable=AsyncMock),
        patch("app.services.ozon_client.WebDriverWait", return_value=mock_wait),
    ):
        result = await fetch_product_info("https://www.ozon.ru/product/test")

        assert result.title == "Test Product"
        assert result.price_with_card is None
        assert result.price_no_card is None


@pytest.mark.asyncio
async def test_fetch_product_info_title_fallback():
    mock_driver = MagicMock()

    mock_wait = MagicMock()
    mock_wait.until.side_effect = Exception("Title not found")

    def mock_find_element(by, xpath):
        if "tsHeadline600Large" in xpath:
            elem = MagicMock()
            elem.text = "999 ₽"
            return elem
        from selenium.common.exceptions import NoSuchElementException

        raise NoSuchElementException("Element not found")

    mock_driver.find_element = mock_find_element

    with (
        patch.object(_SeleniumBrowser, "ensure_started", new_callable=AsyncMock),
        patch.object(_SeleniumBrowser, "get_driver", return_value=mock_driver),
        patch("app.services.ozon_client.asyncio.to_thread", new_callable=AsyncMock),
        patch("app.services.ozon_client.WebDriverWait", return_value=mock_wait),
    ):
        result = await fetch_product_info("https://www.ozon.ru/product/test")

        assert result.title == "Ozon item"
        assert result.price_with_card == Decimal("999")


@pytest.mark.asyncio
async def test_fetch_product_info_retry_logic():
    mock_driver = MagicMock()
    call_count = {"n": 0}

    async def mock_to_thread(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise Exception("Temporary failure")
        return None

    mock_title_element = MagicMock()
    mock_title_element.text = "Retry Success"
    mock_wait = MagicMock()
    mock_wait.until.return_value = mock_title_element

    mock_driver.find_element.side_effect = lambda by, xpath: None

    with (
        patch.object(_SeleniumBrowser, "ensure_started", new_callable=AsyncMock),
        patch.object(_SeleniumBrowser, "get_driver", return_value=mock_driver),
        patch("app.services.ozon_client.asyncio.to_thread", side_effect=mock_to_thread),
        patch("app.services.ozon_client.WebDriverWait", return_value=mock_wait),
        patch("app.services.ozon_client.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await fetch_product_info("https://www.ozon.ru/product/test", retries=2)

        assert result.title == "Retry Success"
        assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_fetch_product_info_all_retries_fail():
    mock_driver = MagicMock()

    async def mock_to_thread(*args, **kwargs):
        raise Exception("Persistent failure")

    with (
        patch.object(_SeleniumBrowser, "ensure_started", new_callable=AsyncMock),
        patch.object(_SeleniumBrowser, "get_driver", return_value=mock_driver),
        patch("app.services.ozon_client.asyncio.to_thread", side_effect=mock_to_thread),
        patch("app.services.ozon_client.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(OzonBlockedError):
            await fetch_product_info("https://www.ozon.ru/product/test", retries=1)


@pytest.mark.asyncio
async def test_shutdown_browser():
    with patch.object(_SeleniumBrowser, "shutdown", new_callable=AsyncMock) as mock_shutdown:
        await shutdown_browser()
        assert mock_shutdown.called
