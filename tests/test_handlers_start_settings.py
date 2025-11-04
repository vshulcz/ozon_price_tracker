import pytest

from app.callbacks import SettingsCB
from app.handlers.settings import change_lang, open_settings, settings_back
from app.handlers.start import cmd_menu, cmd_start


@pytest.mark.asyncio
async def test_cmd_start_ru(dummy_message, users_repo):
    await cmd_start(dummy_message, users_repo)
    assert dummy_message.answers, "ожидали ответ"
    assert "Привет! Я — бот" in dummy_message.answers[0]["text"]


@pytest.mark.asyncio
async def test_cmd_menu_en(dummy_message, users_repo):
    u = await users_repo.ensure_user(dummy_message.from_user.id)
    await users_repo.set_language(u.tg_user_id, "en")
    await cmd_menu(dummy_message, users_repo)
    assert "Hi! I help you track" in dummy_message.answers[0]["text"]


@pytest.mark.asyncio
async def test_open_settings(dummy_cb, users_repo):
    await users_repo.set_language(dummy_cb.from_user.id, "ru")
    await open_settings(dummy_cb, users_repo)
    assert dummy_cb.message.edits, "ожидали edit_text"
    assert "Настройки" in dummy_cb.message.edits[0]["text"]
    assert dummy_cb.answers and dummy_cb.answers[-1]["text"] is None


@pytest.mark.asyncio
async def test_change_lang_to_en(dummy_cb, users_repo):
    await change_lang(dummy_cb, SettingsCB(action="lang", value="en"), users_repo)
    assert dummy_cb.message.edits, "ожидали edit_text"
    assert "Language set to English" in dummy_cb.message.edits[-1]["text"]


@pytest.mark.asyncio
async def test_settings_back_to_main_en(dummy_cb, users_repo):
    await users_repo.set_language(dummy_cb.from_user.id, "en")
    await settings_back(dummy_cb, users_repo)
    assert dummy_cb.message.edits
    assert "Hi! I help you track" in dummy_cb.message.edits[-1]["text"]
