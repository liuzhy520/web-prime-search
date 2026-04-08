from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from web_prime_search.config import Settings
from web_prime_search.engines.google import (
    _build_browser_settings,
    _build_search_url,
    _build_results_from_dom_items,
    _extract_cse_tok,
    _extract_frontend_key,
    _parse_jsonp,
    _run_browser_search,
    _search_via_ajax,
    search,
)

_SETTINGS = Settings(
    google_cx="test-cx",
    proxy_url="http://127.0.0.1:7897",
)


class _AsyncPlaywrightContext:
    def __init__(self, playwright: object) -> None:
        self._playwright = playwright

    async def __aenter__(self) -> object:
        return self._playwright

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _playwright_factory(playwright: object):
    def _factory() -> _AsyncPlaywrightContext:
        return _AsyncPlaywrightContext(playwright)

    return _factory


def test_build_search_url_contains_cx_and_query_hash() -> None:
    url = _build_search_url("test-cx", "geo china")

    assert url.startswith("https://cse.google.com/cse?cx=test-cx")
    assert "gsc.q=geo%20china" in url


def test_build_browser_settings_maps_google_proxy_to_shared_browser_helpers() -> None:
    settings = Settings(
        google_cx="test-cx",
        proxy_url="http://127.0.0.1:7897",
        proxy_engines=["google"],
    )

    browser_settings = _build_browser_settings(settings)

    assert browser_settings.proxy_engines == ["google_html"]


def test_build_results_from_dom_items_filters_invalid_entries() -> None:
    results = _build_results_from_dom_items(
        [
            {
                "href": "https://example.com/1",
                "title": "DOM Result",
                "snippet": "DOM snippet",
            },
            {
                "href": "javascript:void(0)",
                "title": "Ignore me",
                "snippet": "",
            },
            {
                "href": "https://example.com/1",
                "title": "Duplicate",
                "snippet": "",
            },
        ]
    )

    assert len(results) == 1
    assert results[0].title == "DOM Result"


@pytest.mark.asyncio
async def test_search_requires_google_cx() -> None:
    settings = Settings(google_cx="")

    with pytest.raises(ValueError, match="Google CX is not configured"):
        await search("query", settings=settings)


def test_google_live_search_prints_results(capsys: pytest.CaptureFixture[str]) -> None:
    if os.environ.get("WPS_RUN_LIVE_GOOGLE_TEST") != "1":
        pytest.skip("Set WPS_RUN_LIVE_GOOGLE_TEST=1 to run the live Google search test")

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    src_path = str(repo_root / "src")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else os.pathsep.join([src_path, existing_pythonpath])

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "web_prime_search",
            "search",
            "--query",
            "coding plan",
            "--engines",
            "google",
            "--max-results",
            "5",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr

    payload = json.loads(completed.stdout)
    assert payload, "Expected at least one live Google search result"

    with capsys.disabled():
        print(json.dumps(payload, ensure_ascii=False, indent=2))


@patch("web_prime_search.engines.google._save_cookies", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._load_cookies", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._apply_stealth", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._open_browser_context", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_run_browser_search_returns_callback_results(
    mock_open_browser_context: AsyncMock,
    mock_apply_stealth: AsyncMock,
    mock_load_cookies: AsyncMock,
    mock_save_cookies: AsyncMock,
) -> None:
    page = AsyncMock()
    page.evaluate.side_effect = [
        [
            {
                "href": "https://example.com/1",
                "title": "Example Result",
                "snippet": "Example snippet",
            }
        ],
    ]
    page.content.return_value = "<html></html>"

    context = AsyncMock()
    context.pages = []
    context.new_page.return_value = page
    mock_open_browser_context.return_value = (context, None)

    results = await _run_browser_search(
        query="test query",
        max_results=5,
        settings=_SETTINGS,
        async_playwright=_playwright_factory(object()),
        playwright_timeout_error=TimeoutError,
    )

    assert len(results) == 1
    assert results[0].title == "Example Result"
    assert results[0].source == "google"
    page.goto.assert_awaited_once()
    mock_apply_stealth.assert_awaited_once()
    mock_load_cookies.assert_awaited_once()
    mock_save_cookies.assert_awaited_once()


@patch("web_prime_search.engines.google._save_cookies", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._load_cookies", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._apply_stealth", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._open_browser_context", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_run_browser_search_falls_back_to_dom_results(
    mock_open_browser_context: AsyncMock,
    mock_apply_stealth: AsyncMock,
    mock_load_cookies: AsyncMock,
    mock_save_cookies: AsyncMock,
) -> None:
    page = AsyncMock()
    page.wait_for_function.side_effect = [TimeoutError(), None]
    page.evaluate.side_effect = [[
        {
            "href": "https://example.com/dom",
            "title": "DOM Result",
            "snippet": "DOM snippet",
        }
    ]]
    page.content.return_value = "<html><body><div class='gsc-results'></div></body></html>"

    context = AsyncMock()
    context.pages = []
    context.new_page.return_value = page
    mock_open_browser_context.return_value = (context, None)

    results = await _run_browser_search(
        query="test query",
        max_results=5,
        settings=_SETTINGS,
        async_playwright=_playwright_factory(object()),
        playwright_timeout_error=TimeoutError,
    )

    assert len(results) == 1
    assert results[0].url == "https://example.com/dom"
    page.fill.assert_awaited_once_with("input.gsc-input[name='search']", "test query")
    page.click.assert_awaited_once()
    mock_apply_stealth.assert_awaited_once()
    mock_load_cookies.assert_awaited_once()
    mock_save_cookies.assert_awaited_once()


@patch("web_prime_search.engines.google._save_cookies", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._load_cookies", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._apply_stealth", new_callable=AsyncMock)
@patch("web_prime_search.engines.google._open_browser_context", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_run_browser_search_detects_blocked_page_after_empty_callback(
    mock_open_browser_context: AsyncMock,
    mock_apply_stealth: AsyncMock,
    mock_load_cookies: AsyncMock,
    mock_save_cookies: AsyncMock,
) -> None:
    page = AsyncMock()
    page.wait_for_function.side_effect = [None]
    page.evaluate.return_value = []
    page.content.return_value = "<html><body>unusual traffic</body></html>"

    context = AsyncMock()
    context.pages = []
    context.new_page.return_value = page
    mock_open_browser_context.return_value = (context, None)

    with pytest.raises(ValueError, match="Google CSE search blocked by anti-bot or consent page"):
        await _run_browser_search(
            query="test query",
            max_results=5,
            settings=_SETTINGS,
            async_playwright=_playwright_factory(object()),
            playwright_timeout_error=TimeoutError,
        )

    mock_apply_stealth.assert_awaited_once()
    mock_load_cookies.assert_awaited_once()
    mock_save_cookies.assert_awaited_once()


# ---------------------------------------------------------------------------
# AJAX path tests
# ---------------------------------------------------------------------------

_FAKE_CSE_JS = (
    'var a={"cse_tok":"fake-tok-abc","key":"AIzaSyFAKEKEY123456789012345678901234","cx":"test-cx"};'
)

_FAKE_JSONP = (
    'google.search.cse.api0({"cursor":{"resultCount":"42"},"results":['
    '{"unescapedUrl":"https://example.com/1","titleNoFormatting":"Result One","content":"Snip one"},'
    '{"unescapedUrl":"https://example.com/2","titleNoFormatting":"Result Two","content":"Snip two"}'
    ']})'
)

_CSE_JS_URL = "https://cse.google.com/cse.js"
_CSE_ELEMENT_URL = "https://www.googleapis.com/customsearch/v1element"


def test_extract_cse_tok_parses_value() -> None:
    tok = _extract_cse_tok(_FAKE_CSE_JS)
    assert tok == "fake-tok-abc"


def test_extract_cse_tok_returns_empty_on_miss() -> None:
    assert _extract_cse_tok("no tok here") == ""


def test_extract_frontend_key_parses_value() -> None:
    key = _extract_frontend_key(_FAKE_CSE_JS)
    assert key == "AIzaSyFAKEKEY123456789012345678901234"


def test_extract_frontend_key_returns_empty_on_miss() -> None:
    assert _extract_frontend_key("no key here") == ""


def test_parse_jsonp_valid() -> None:
    data = _parse_jsonp(_FAKE_JSONP)
    assert data["cursor"]["resultCount"] == "42"
    assert len(data["results"]) == 2


def test_parse_jsonp_returns_empty_on_garbage() -> None:
    assert _parse_jsonp("not jsonp at all") == {}
    assert _parse_jsonp("fn({bad json})") == {}
    assert _parse_jsonp("") == {}


@respx.mock
@pytest.mark.asyncio
async def test_search_via_ajax_returns_results() -> None:
    respx.get(_CSE_JS_URL).mock(return_value=Response(200, text=_FAKE_CSE_JS))
    respx.get(_CSE_ELEMENT_URL).mock(return_value=Response(200, text=_FAKE_JSONP))

    results = await _search_via_ajax("python tips", 5, _SETTINGS)

    assert len(results) == 2
    assert results[0].url == "https://example.com/1"
    assert results[0].title == "Result One"
    assert results[0].snippet == "Snip one"
    assert results[0].source == "google"
    assert results[1].url == "https://example.com/2"


@respx.mock
@pytest.mark.asyncio
async def test_search_via_ajax_raises_on_js_fetch_failure() -> None:
    respx.get(_CSE_JS_URL).mock(return_value=Response(403, text="Forbidden"))

    with pytest.raises(ValueError, match="Google CSE JS fetch failed"):
        await _search_via_ajax("query", 5, _SETTINGS)


@respx.mock
@pytest.mark.asyncio
async def test_search_via_ajax_raises_when_tok_missing() -> None:
    respx.get(_CSE_JS_URL).mock(return_value=Response(200, text="var a = {};"))

    with pytest.raises(ValueError, match="could not extract cse_tok or key"):
        await _search_via_ajax("query", 5, _SETTINGS)


@respx.mock
@pytest.mark.asyncio
async def test_search_via_ajax_raises_on_element_api_failure() -> None:
    respx.get(_CSE_JS_URL).mock(return_value=Response(200, text=_FAKE_CSE_JS))
    respx.get(_CSE_ELEMENT_URL).mock(return_value=Response(429, text="Rate limited"))

    with pytest.raises(ValueError, match="Google CSE element API failed"):
        await _search_via_ajax("query", 5, _SETTINGS)


@respx.mock
@pytest.mark.asyncio
async def test_search_via_ajax_raises_on_empty_and_no_cursor() -> None:
    empty_jsonp = 'google.search.cse.api0({"results":[]})'
    respx.get(_CSE_JS_URL).mock(return_value=Response(200, text=_FAKE_CSE_JS))
    respx.get(_CSE_ELEMENT_URL).mock(return_value=Response(200, text=empty_jsonp))

    with pytest.raises(ValueError, match="empty response with no cursor"):
        await _search_via_ajax("query", 5, _SETTINGS)


@respx.mock
@pytest.mark.asyncio
async def test_search_uses_ajax_path_when_available() -> None:
    """search() should use the AJAX path and NOT launch a browser when it succeeds."""
    respx.get(_CSE_JS_URL).mock(return_value=Response(200, text=_FAKE_CSE_JS))
    respx.get(_CSE_ELEMENT_URL).mock(return_value=Response(200, text=_FAKE_JSONP))

    with patch("web_prime_search.engines.google._search_via_browser") as mock_browser:
        results = await search("python", settings=_SETTINGS)

    assert len(results) == 2
    mock_browser.assert_not_called()


@respx.mock
@pytest.mark.asyncio
async def test_search_falls_back_to_browser_when_ajax_fails() -> None:
    """When AJAX raises, search() falls back to the Playwright browser."""
    from web_prime_search.models import SearchResult

    respx.get(_CSE_JS_URL).mock(return_value=Response(503, text="Service Unavailable"))

    browser_result = [
        SearchResult(
            title="Browser Result",
            url="https://example.com/b",
            snippet="b snip",
            source="google",
        )
    ]

    with patch(
        "web_prime_search.engines.google._search_via_browser",
        new_callable=AsyncMock,
        return_value=browser_result,
    ) as mock_browser:
        results = await search("python", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].title == "Browser Result"
    mock_browser.assert_awaited_once()

