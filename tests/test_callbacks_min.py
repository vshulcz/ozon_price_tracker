from app.callbacks import ActionCB, MenuCB, ProductCB, SettingsCB


def test_callback_pack_basic():
    s = MenuCB(action="list", page=2).pack()
    assert isinstance(s, str) and s.startswith("menu:")
    s2 = SettingsCB(action="lang", value="en").pack()
    assert s2.startswith("settings:")
    s3 = ActionCB(action="cancel").pack()
    assert s3.startswith("action:")
    s4 = ProductCB(action="open", id=42, page=3).pack()
    assert s4.startswith("product:")
