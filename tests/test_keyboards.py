from app.i18n import i18n
from app.keyboards.common import cancel_kb
from app.keyboards.main import main_menu_kb, settings_kb
from app.keyboards.products import product_card_kb, products_list_kb


def _flat_texts(markup):
    return [btn.text for row in markup.inline_keyboard for btn in row]


def test_main_menu_kb_ru():
    kb = main_menu_kb(i18n, "ru")
    texts = _flat_texts(kb)
    assert "➕ Добавить товар" in texts  # noqa: RUF001
    assert "📋 Список товаров" in texts
    assert "⚙️ Настройки" in texts


def test_settings_kb_en():
    kb = settings_kb(i18n, "en")
    texts = _flat_texts(kb)
    assert "🇷🇺 Russian" in texts
    assert "🇬🇧 English" in texts
    assert "🏠 Main menu" in texts


def test_cancel_kb():
    kb = cancel_kb(i18n, "ru")
    texts = _flat_texts(kb)
    assert "❌ Отмена" in texts


def test_products_list_nav_and_back():
    kb = products_list_kb(i18n, "ru", items=[(1, "Item 1"), (2, "Item 2")], page=2, pages=3)
    texts = _flat_texts(kb)
    assert "Item 1" in texts and "Item 2" in texts
    assert "◀️" in texts and "▶️" in texts
    assert "🏠 В главное меню" in texts  # noqa: RUF001


def test_product_card_kb_en():
    kb = product_card_kb(i18n, "en", product_id=1, page=1, url="https://www.ozon.ru/item/1")
    texts = _flat_texts(kb)
    assert "✏️ Edit target price" in texts
    assert "🗑️ Remove" in texts
    assert "⬅️ Назад" in texts
    assert "🏠 Main menu" in texts
