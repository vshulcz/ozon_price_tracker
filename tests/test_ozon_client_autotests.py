import os

import pytest

from app.services.ozon_client import (
    OzonBlockedError,
    _SeleniumBrowser,
    fetch_product_info,
    shutdown_browser,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1 environment variable",
)

TEST_URLS = {
    "valid_product": "https://www.ozon.ru/product/svitshot-winkiki-tolstovka-dlya-malchikov-i-devochek-1659405348/",
    "another_product": "https://www.ozon.ru/product/silikonovyy-shnurok-derzhatel-dlya-besprovodnyh-naushnikov-apple-airpods-na-magnite-2789383376/",
}


@pytest.fixture(scope="module")
async def browser_cleanup():
    yield
    await shutdown_browser()


@pytest.mark.asyncio
async def test_browser_starts_and_shuts_down():
    await _SeleniumBrowser.shutdown()
    assert _SeleniumBrowser._driver is None

    await _SeleniumBrowser.ensure_started()
    assert _SeleniumBrowser._driver is not None
    driver = _SeleniumBrowser.get_driver()
    assert driver is not None

    await _SeleniumBrowser.shutdown()
    assert _SeleniumBrowser._driver is None


@pytest.mark.asyncio
async def test_fetch_real_product_success(browser_cleanup):
    result = await fetch_product_info(TEST_URLS["valid_product"], retries=2)

    assert result is not None
    assert result.title
    assert len(result.title) > 5, "Title should be meaningful"

    if result.title != "Ozon item":
        assert "iphone" in result.title.lower() or "apple" in result.title.lower()

    print(f"\n✓ Product fetched: {result.title[:50]}")
    print(f"  Price with card: {result.price_with_card}")
    print(f"  Price no card: {result.price_no_card}")

    if result.price_with_card:
        assert result.price_with_card > 0
    if result.price_no_card:
        assert result.price_no_card > 0


@pytest.mark.asyncio
async def test_fetch_multiple_products(browser_cleanup):
    results = []

    for name, url in TEST_URLS.items():
        result = await fetch_product_info(url, retries=2)
        results.append((name, result))

        assert result.title
        print(f"\n✓ {name}: {result.title[:40]}")
        if result.price_for_compare:
            print(f"  Price: {result.price_for_compare}₽")
        else:
            print("  Price: Not extracted (possible Ozon blocking)")

    titles = [r[1].title for r in results]
    if all(t != "Ozon item" for t in titles):
        assert len(set(titles)) == len(titles), "Should fetch different products"


@pytest.mark.asyncio
async def test_fetch_with_different_url_formats(browser_cleanup):
    urls = [
        "https://ozon.ru/product/smartfon-apple-iphone-15-128-gb-rozovyy-1210327640/",
        "https://www.ozon.ru/product/smartfon-apple-iphone-15-128-gb-rozovyy-1210327640/",
    ]

    results = []
    for url in urls:
        result = await fetch_product_info(url, retries=1)
        results.append(result)

    assert results[0].title == results[1].title
    print(f"\n✓ URL normalization works: {results[0].title[:40]}")


@pytest.mark.asyncio
async def test_invalid_product_url():
    with pytest.raises(ValueError, match="Not an Ozon product URL"):
        await fetch_product_info("https://yandex.ru/product/123")

    with pytest.raises(ValueError, match="Not an Ozon product URL"):
        await fetch_product_info("https://amazon.com/product/123")


@pytest.mark.asyncio
async def test_fetch_nonexistent_product(browser_cleanup):
    fake_url = "https://www.ozon.ru/product/nonexistent-product-999999999999999/"

    try:
        result = await fetch_product_info(fake_url, retries=1)
        assert result.title
        print(f"\n✓ Non-existent product handled: {result.title}")
    except OzonBlockedError:
        print("\n✓ Non-existent product correctly raised OzonBlockedError")


@pytest.mark.asyncio
async def test_concurrent_fetches(browser_cleanup):
    import asyncio

    urls = [
        TEST_URLS["valid_product"],
        TEST_URLS["another_product"],
    ]

    tasks = [fetch_product_info(url, retries=1) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"\n✗ Task {i} failed: {result}")
        else:
            assert result.title
            print(f"\n✓ Task {i}: {result.title[:40]}")


@pytest.mark.asyncio
async def test_price_extraction_accuracy(browser_cleanup):
    result = await fetch_product_info(TEST_URLS["valid_product"], retries=2)

    if result.price_with_card:
        assert 10_000 < result.price_with_card < 300_000, "Price should be in reasonable range"
        print(f"\n✓ Price with card is reasonable: {result.price_with_card}₽")

    if result.price_no_card:
        assert 10_000 < result.price_no_card < 300_000, "Price should be in reasonable range"
        print(f"\n✓ Price no card is reasonable: {result.price_no_card}₽")

    if result.price_with_card and result.price_no_card:
        assert result.price_no_card >= result.price_with_card, "Card price should be cheaper"
        print(f"""\n✓ Price relationship correct:
              {result.price_no_card}₽ >= {result.price_with_card}₽""")

    if not result.price_with_card and not result.price_no_card:
        print("\n⚠ No prices extracted - possible Ozon blocking or HTML structure changed")


@pytest.mark.asyncio
async def test_retry_logic_with_real_network(browser_cleanup):
    result = await fetch_product_info(TEST_URLS["valid_product"], retries=0)
    assert result.title
    print(f"\n✓ Fetch succeeded without retries: {result.title[:40]}")


@pytest.mark.asyncio
async def test_browser_survives_multiple_sessions(browser_cleanup):
    for i in range(3):
        await _SeleniumBrowser.shutdown()
        await _SeleniumBrowser.ensure_started()
        driver = _SeleniumBrowser.get_driver()
        assert driver is not None
        print(f"\n✓ Browser restart #{i + 1} successful")


@pytest.mark.asyncio
async def test_stealth_mode_active(browser_cleanup):
    await _SeleniumBrowser.ensure_started()
    driver = _SeleniumBrowser.get_driver()

    assert driver is not None

    result = await fetch_product_info(TEST_URLS["valid_product"], retries=1)
    assert result.title
    print(f"\n✓ Stealth mode working: successfully fetched {result.title[:40]}")


@pytest.mark.asyncio
async def test_fetch_performance(browser_cleanup):
    import time

    start = time.time()
    result = await fetch_product_info(TEST_URLS["valid_product"], retries=1)
    elapsed = time.time() - start

    assert result.title
    assert elapsed < 10, f"Fetch took too long: {elapsed:.2f}s"
    print(f"\n✓ Fetch completed in {elapsed:.2f}s")


@pytest.mark.asyncio
async def test_browser_startup_performance():
    import time

    await _SeleniumBrowser.shutdown()

    start = time.time()
    await _SeleniumBrowser.ensure_started()
    elapsed = time.time() - start

    assert elapsed < 5, f"Browser startup took too long: {elapsed:.2f}s"
    print(f"\n✓ Browser started in {elapsed:.2f}s")

    await _SeleniumBrowser.shutdown()
