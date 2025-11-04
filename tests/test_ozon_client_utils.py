from decimal import Decimal

from app.services.ozon_client import _normalize_price, _to_www


def test_normalize_price():
    vals = [
        _normalize_price("1 999,90 ₽"),
        _normalize_price("1 999.90 руб"),  # noqa: RUF001
        _normalize_price("1999.90"),
        _normalize_price("  1 999,90"),
    ]
    assert all(v == Decimal("1999.90") for v in vals)


def test_to_www_normalizes_host():
    assert _to_www("https://ozon.ru/item/42").startswith("https://www.ozon.ru/")
    assert _to_www("https://sub.ozon.ru/item/42").startswith("https://www.ozon.ru/")
    assert _to_www("http://www.ozon.ru/item/42").startswith("http://www.ozon.ru/")
