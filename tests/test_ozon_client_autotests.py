import asyncio
import json
from decimal import Decimal
from typing import Any, cast

import pytest

import app.services.ozon_client as oc


class FakeResponseOK:
    def __init__(self, payload):
        self.ok = True
        self._payload = payload

    async def json(self):
        return self._payload


class FakeResponseBad:
    def __init__(self):
        self.ok = False

    async def json(self):
        raise RuntimeError("should not be called")


class FakeRequestClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def get(self, url, headers=None):
        self.calls.append((url, headers))
        return self._response


class FakePage:
    def __init__(self, ctx):
        self.ctx = ctx
        self.closed = False
        self.goto_calls = []
        self._expect_should_raise = False

    async def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append((url, wait_until, timeout))

    class _ExpectCtx:
        def __init__(self, should_raise: bool):
            self.should_raise = should_raise
            self.value = None

        async def __aenter__(self):
            if self.should_raise:
                raise Exception("timeout")
            self.value = asyncio.sleep(0)
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def expect_response(self, predicate, timeout=None):
        return FakePage._ExpectCtx(should_raise=self._expect_should_raise)

    async def close(self):
        self.closed = True


class FakeContext:
    def __init__(self):
        self._cookies = [{"name": "abt_data"}]
        self._script = None
        self._route = None
        self._pattern = None
        self.request = FakeRequestClient(FakeResponseOK({"ok": True}))
        self.created_pages = []
        self.closed = False

    async def new_page(self):
        p = FakePage(self)
        self.created_pages.append(p)
        return p

    async def cookies(self, domain):
        return list(self._cookies)

    async def add_init_script(self, script):
        self._script = script

    async def route(self, pattern, handler):
        self._pattern = pattern
        self._route = handler

    async def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context: FakeContext):
        self._ctx = context
        self.closed = False

    async def new_context(self, **kwargs):
        return self._ctx

    async def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser_to_return: FakeBrowser, fail_on_channel_first=True):
        self.browser_to_return = browser_to_return
        self.launch_calls = []
        self._fail_on_channel_first = fail_on_channel_first
        self._first_try = True

    async def launch(self, **kwargs):
        self.launch_calls.append(kwargs)
        if self._fail_on_channel_first and kwargs.get("channel") and self._first_try:
            self._first_try = False
            raise RuntimeError("channel not available")
        return self.browser_to_return


class FakePlaywright:
    def __init__(self, chromium: FakeChromium):
        self.chromium = chromium
        self.stopped = False

    async def start(self):
        return self

    async def stop(self):
        self.stopped = True


def make_widget_states(*pairs):
    return {k: json.dumps(v, ensure_ascii=False) for k, v in pairs}


@pytest.mark.asyncio
async def test_browser_ensure_started_fallback_and_shutdown(monkeypatch):
    monkeypatch.setattr(
        oc,
        "_os_profile",
        lambda: {
            "ua": "UA",
            "platform_js": "MacIntel",
            "args": ["--lang=ru-RU"],
            "channel": "chrome",
        },
    )

    fake_ctx = FakeContext()
    fake_browser = FakeBrowser(fake_ctx)
    fake_chromium = FakeChromium(fake_browser, fail_on_channel_first=True)
    fake_pl = FakePlaywright(fake_chromium)

    monkeypatch.setattr(oc, "async_playwright", lambda: fake_pl)

    await oc._Browser.shutdown()

    await oc._Browser.ensure_started()
    assert oc._Browser._ctx is fake_ctx
    assert fake_ctx._route is oc._route_blocker
    p = await oc._Browser.page()
    assert isinstance(p, FakePage)

    await oc._Browser.shutdown()
    assert fake_browser.closed
    assert fake_pl.stopped
    assert oc._Browser._ctx is None
    assert oc._Browser._browser is None
    assert oc._Browser._pl is None


class DummyRoute:
    def __init__(self):
        self.continued = 0
        self.aborted = 0

    async def continue_(self):
        self.continued += 1

    async def abort(self):
        self.aborted += 1


class DummyRequest:
    def __init__(self, url, resource_type="document"):
        self.url = url
        self.resource_type = resource_type


@pytest.mark.asyncio
async def test_route_blocker_first_party():
    r = DummyRoute()
    req = DummyRequest("https://www.ozon.ru/page")
    await oc._route_blocker(r, req)
    assert r.continued == 1 and r.aborted == 0


@pytest.mark.asyncio
async def test_route_blocker_media_abort_third_party():
    r = DummyRoute()
    req = DummyRequest("https://cdn.external.com/video.mp4", resource_type="media")
    await oc._route_blocker(r, req)
    assert r.aborted == 1


@pytest.mark.asyncio
async def test_route_blocker_third_party_non_media_continue():
    r = DummyRoute()
    req = DummyRequest("https://example.com/script.js", resource_type="script")
    await oc._route_blocker(r, req)
    assert r.continued == 1


@pytest.mark.asyncio
async def test_pass_ozon_challenge_ok():
    ctx = FakeContext()
    page = await ctx.new_page()
    ok = await oc._pass_ozon_challenge(cast(Any, ctx), cast(Any, page), timeout_ms=10_000)
    assert ok is True
    assert page.goto_calls, "ожидали заход на abt-страницу"


@pytest.mark.asyncio
async def test_pass_ozon_challenge_fail_on_timeout_or_no_cookie():
    ctx = FakeContext()
    page = await ctx.new_page()
    page._expect_should_raise = True
    ok = await oc._pass_ozon_challenge(cast(Any, ctx), cast(Any, page), timeout_ms=10_000)
    assert ok is False

    page = await ctx.new_page()
    ctx._cookies = []
    ok2 = await oc._pass_ozon_challenge(cast(Any, ctx), cast(Any, page), timeout_ms=10_000)
    assert ok2 is False


@pytest.mark.asyncio
async def test_ozon_api_get_json_v2_ok():
    ctx = FakeContext()
    payload = {"hello": "world"}
    ctx.request = FakeRequestClient(FakeResponseOK(payload))
    data = await oc._ozon_api_get_json_v2(ctx, "https://www.ozon.ru/product/abc?q=1")
    assert data == payload


@pytest.mark.asyncio
async def test_ozon_api_get_json_v2_not_ok_or_json_error():
    ctx = FakeContext()
    ctx.request = FakeRequestClient(FakeResponseBad())
    data = await oc._ozon_api_get_json_v2(ctx, "https://www.ozon.ru/product/abc")
    assert data is None

    class _Resp(FakeResponseOK):
        async def json(self):
            raise RuntimeError("boom")

    ctx.request = FakeRequestClient(_Resp({"ignored": True}))
    data2 = await oc._ozon_api_get_json_v2(ctx, "https://www.ozon.ru/product/abc")
    assert data2 is None


def test_iter_widget_objs_and_predicates():
    ws = {"webProductHeading-1": json.dumps({"title": "T"}), "notjson": {"x": 1}}
    objs = list(oc._iter_widget_objs(ws))
    assert len(objs) == 1 and objs[0][0].startswith("webProductHeading")
    assert oc._is_title_widget(objs[0][0]) is True
    assert oc._is_price_widget("webProductPrices-foo") is True
    assert oc._is_price_widget("random") is False


def test_pick_title_routes():
    data = {
        "widgetStates": make_widget_states(("webProductHeading-1", {"title": "FromWidget"})),
        "seo": {"title": "FromSEO"},
    }
    assert oc._pick_title(data) == "FromWidget"

    data2 = {"widgetStates": {}, "seo": {"title": "FromSEO"}}
    assert oc._pick_title(data2) == "FromSEO"

    data3 = {
        "widgetStates": make_widget_states(
            ("x", {"cellTrackingInfo": {"product": {"title": "FromCell"}}})
        )
    }
    assert oc._pick_title(data3) == "FromCell"


def test_pick_prices_widget_and_fallback_ruble():
    data = {
        "widgetStates": make_widget_states(
            (
                "webProductPrices-1",
                {"price": "1 999,90", "cardPrice": "1 899,90", "isAvailable": True},
            )
        )
    }
    with_card, no_card = oc._pick_prices(data)
    assert with_card == Decimal("1899.90") and no_card == Decimal("1999.90")

    data2 = {
        "widgetStates": {},
        "seo": {"title": "X"},
        "randomDump": "Цена сейчас 1 299 ₽, без карты 1 499 ₽",
    }
    wc, nc = oc._pick_prices(data2)
    assert wc in (Decimal("1299"), Decimal("1499"))
    assert nc in (Decimal("1299"), Decimal("1499"))
    assert wc != nc


@pytest.mark.asyncio
async def test_fetch_product_info_via_api_happy(monkeypatch):
    fake_ctx = FakeContext()
    payload = {
        "widgetStates": make_widget_states(
            ("webProductHeading-1", {"title": "Awesome Chair"}),
            (
                "webProductPrices-1",
                {"price": "2 499,00", "cardPrice": "2 199,00", "isAvailable": True},
            ),
        ),
        "seo": {"title": "Ignored"},
    }
    fake_ctx.request = FakeRequestClient(FakeResponseOK(payload))

    async def fake_ensure_started():
        oc._Browser._ctx = cast(Any, fake_ctx)

    monkeypatch.setattr(oc._Browser, "ensure_started", fake_ensure_started)

    monkeypatch.setattr(oc._Browser, "_ctx", fake_ctx, raising=False)

    info = await oc.fetch_product_info_via_api("https://ozon.ru/product/whatever")
    assert info.title == "Awesome Chair"
    assert info.price_with_card == Decimal("2199.00")
    assert info.price_no_card == Decimal("2499.00")
    assert info.price_for_compare == Decimal("2199.00")


@pytest.mark.asyncio
async def test_fetch_product_info_via_api_ozon_empty(monkeypatch):
    fake_ctx = FakeContext()
    fake_ctx.request = FakeRequestClient(FakeResponseOK(None))

    async def fake_ensure_started():
        oc._Browser._ctx = cast(Any, fake_ctx)

    monkeypatch.setattr(oc._Browser, "ensure_started", fake_ensure_started)
    monkeypatch.setattr(oc._Browser, "_ctx", fake_ctx, raising=False)

    with pytest.raises(oc.OzonBlockedError):
        await oc.fetch_product_info_via_api("https://www.ozon.ru/product/abc")


@pytest.mark.asyncio
async def test_fetch_product_info_retries_and_success(monkeypatch):
    class _P:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    pages = []

    async def fake_page():
        p = _P()
        pages.append(p)
        return p

    monkeypatch.setattr(oc._Browser, "page", fake_page)

    calls = {"n": 0}

    async def fake_via_api(url):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return oc.ProductInfo(title="X", price_no_card=Decimal("10.00"), price_with_card=None)

    monkeypatch.setattr(oc, "fetch_product_info_via_api", fake_via_api)

    info = await oc.fetch_product_info("https://www.ozon.ru/product/x", retries=2)
    assert info.title == "X" and info.price_for_compare == Decimal("10.00")
    assert all(p.closed for p in pages)


@pytest.mark.asyncio
async def test_fetch_product_info_invalid_url_and_blocked(monkeypatch):
    with pytest.raises(ValueError):
        await oc.fetch_product_info("https://example.com/not-ozon")

    class _P:
        async def close(self):
            pass

    async def fake_page():
        return _P()

    monkeypatch.setattr(oc._Browser, "page", fake_page)

    async def always_fail(url):
        raise RuntimeError("nope")

    monkeypatch.setattr(oc, "fetch_product_info_via_api", always_fail)

    with pytest.raises(oc.OzonBlockedError):
        await oc.fetch_product_info("https://www.ozon.ru/product/x", retries=1)


def test_to_www_and_normalize_price_and_os_profile(monkeypatch):
    assert oc._to_www("https://ozon.ru/item/42").startswith("https://www.ozon.ru/")
    assert oc._to_www("http://sub.ozon.ru/item/42").startswith("http://www.ozon.ru/")
    assert oc._normalize_price("1 999,90 ₽") == Decimal("1999.90")
    assert oc._normalize_price("abc") is None

    monkeypatch.setattr(oc.platform, "system", lambda: "Linux")
    prof = oc._os_profile()
    assert prof["channel"] is None and "--no-sandbox" in prof["args"][0]

    monkeypatch.setattr(oc.platform, "system", lambda: "Darwin")
    prof2 = oc._os_profile()
    assert prof2["channel"] == "chrome"

    monkeypatch.setattr(oc.platform, "system", lambda: "Windows")
    prof3 = oc._os_profile()
    assert prof3["channel"] == "chrome"
