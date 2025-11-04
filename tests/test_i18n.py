from app.i18n import i18n


def test_i18n_basic_ru():
    msg = i18n.t("ru", "settings.title")
    assert "Настройки" in msg


def test_i18n_basic_en():
    msg = i18n.t("en", "settings.title")
    assert "Settings" in msg


def test_i18n_fallback_to_default_when_key_missing():
    key = "non.existent.key"
    msg_ru = i18n.t("ru", key)
    assert msg_ru == key
    msg_en = i18n.t("en", key)
    assert msg_en == key


def test_i18n_lang_normalization():
    msg = i18n.t("de", "settings.title")  # type: ignore
    assert "Настройки" in msg
