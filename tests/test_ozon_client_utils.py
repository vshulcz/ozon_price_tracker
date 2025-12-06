from decimal import Decimal

import pytest

from app.services.ozon_client import (
    OzonProductInfo,
    _normalize_price,
    _to_www,
    fetch_product_info,
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
    info1 = OzonProductInfo(
        title="Test", price_with_card=Decimal("100"), price_no_card=Decimal("150")
    )
    assert info1.price_for_compare == Decimal("100")

    info2 = OzonProductInfo(title="Test", price_with_card=None, price_no_card=Decimal("150"))
    assert info2.price_for_compare == Decimal("150")

    info3 = OzonProductInfo(title="Test", price_with_card=Decimal("100"), price_no_card=None)
    assert info3.price_for_compare == Decimal("100")

    info4 = OzonProductInfo(title="Test", price_with_card=None, price_no_card=None)
    assert info4.price_for_compare is None


@pytest.mark.asyncio
async def test_fetch_product_info_invalid_url():
    with pytest.raises(ValueError, match="Not an Ozon product URL"):
        await fetch_product_info("https://example.com/product")

    with pytest.raises(ValueError, match="Not an Ozon product URL"):
        await fetch_product_info("https://amazon.com/item")
