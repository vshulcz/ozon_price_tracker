from decimal import Decimal

import pytest

from app.utils.validators import is_ozon_url, parse_price


@pytest.mark.parametrize(
    "url, ok",
    [
        ("https://www.ozon.ru/product/abc", True),
        ("http://ozon.ru/some/path", True),
        ("https://m.ozon.ru/item/1", False),
        ("https://not-ozon.ru/", False),
        ("", False),
        ("ftp://ozon.ru/what", False),
    ],
)
def test_is_ozon_url(url, ok):
    assert is_ozon_url(url) is ok


@pytest.mark.parametrize(
    "text, value",
    [
        ("1999", Decimal("1999.00")),
        ("1 999,9", Decimal("1999.90")),
        ("  2,50 ", Decimal("2.50")),
        ("0.01", Decimal("0.01")),
    ],
)
def test_parse_price_ok(text, value):
    assert parse_price(text) == value


@pytest.mark.parametrize("text", ["0", "-1", "abc", "", " ", ",,,", "0,00"])
def test_parse_price_bad(text):
    assert parse_price(text) is None
