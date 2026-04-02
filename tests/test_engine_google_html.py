from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from web_prime_search.config import Settings
from web_prime_search.engines.google_html import (
    _build_context_kwargs,
    _load_cookies,
    _normalize_cookie_payload,
    _open_browser_context,
    _resolve_profile_dir,
    _save_cookies,
    search,
)
from web_prime_search.models import SearchResult

_SEARCH_URL = "https://www.google.com/search"
_SETTINGS = Settings(proxy_url="http://127.0.0.1:7897")


def _result_block(href: str, title: str, snippet: str) -> str:
    return (
        '<div class="MjjYud">'
        f'<a href="{href}"><h3>{title}</h3></a>'
        f'<div class="VwiC3b">{snippet}</div>'
        "</div>"
    )


@pytest.mark.asyncio
@respx.mock
async def test_search_returns_results_from_html() -> None:
    html = "".join(
        [
            _result_block(
                "https://example.com/first",
                "First <em>Result</em>",
                "First snippet",
            ),
            _result_block(
                "/url?q=https%3A%2F%2Fexample.com%2Fsecond&sa=U&ved=1",
                "Second Result",
                "Second <b>snippet</b>",
            ),
        ]
    )
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    results = await search("test query", settings=_SETTINGS)

    assert len(results) == 2
    assert results[0].source == "google_html"
    assert results[0].title == "First Result"
    assert results[0].url == "https://example.com/first"
    assert results[0].snippet == "First snippet"
    assert results[1].url == "https://example.com/second"
    assert results[1].snippet == "Second snippet"


@pytest.mark.asyncio
@respx.mock
async def test_search_respects_max_results() -> None:
    html = "".join(
        _result_block(f"https://example.com/{index}", f"Result {index}", f"Snippet {index}")
        for index in range(3)
    )
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    results = await search("test query", max_results=2, settings=_SETTINGS)

    assert len(results) == 2


@pytest.mark.asyncio
@respx.mock
async def test_search_deduplicates_urls() -> None:
    html = "".join(
        [
            _result_block("https://example.com/dup", "First", "Snippet 1"),
            _result_block("https://example.com/dup", "Second", "Snippet 2"),
        ]
    )
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    results = await search("test query", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].title == "First"


@pytest.mark.asyncio
@respx.mock
async def test_search_ignores_google_internal_links() -> None:
    html = "".join(
        [
            _result_block("https://www.google.com/preferences", "Internal", "Ignore me"),
            _result_block("/search?q=still+internal", "Also Internal", "Ignore me too"),
            _result_block("https://example.com/live", "External", "Keep me"),
        ]
    )
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    results = await search("test query", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].url == "https://example.com/live"


@pytest.mark.asyncio
@respx.mock
async def test_search_empty_results() -> None:
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text="<html><body>No results</body></html>"))

    results = await search("nothing", settings=_SETTINGS)

    assert results == []


@pytest.mark.asyncio
@respx.mock
async def test_search_http_error() -> None:
    respx.get(_SEARCH_URL).mock(return_value=Response(503))

    with pytest.raises(ValueError, match="Google HTML search error: HTTP 503"):
        await search("query", settings=_SETTINGS)


@pytest.mark.asyncio
@respx.mock
async def test_search_detects_blocked_page() -> None:
    html = "<html><body>Our systems have detected unusual traffic from your computer network.</body></html>"
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    with pytest.raises(
        ValueError,
        match="Google HTML search blocked by anti-bot or consent page",
    ):
        await search("query", settings=_SETTINGS)


@pytest.mark.asyncio
@respx.mock
async def test_search_detects_enablejs_page() -> None:
    html = (
        '<html><body><noscript><meta content="0;url=/httpservice/retry/enablejs?sei=test" '
        'http-equiv="refresh"></noscript></body></html>'
    )
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    with pytest.raises(
        ValueError,
        match="Google HTML search blocked by anti-bot or consent page",
    ):
        await search("query", settings=_SETTINGS)


@pytest.mark.asyncio
@patch("web_prime_search.engines.google_html._search_via_browser", new_callable=AsyncMock)
@respx.mock
async def test_search_falls_back_to_browser_when_static_page_blocked(mock_browser: AsyncMock) -> None:
    html = '<html><body><noscript><meta content="0;url=/httpservice/retry/enablejs?sei=test" http-equiv="refresh"></noscript></body></html>'
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))
    mock_browser.return_value = [
        SearchResult(
            title="Browser Result",
            url="https://example.com/browser",
            snippet="Rendered snippet",
            source="google_html",
        )
    ]

    results = await search("query", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].title == "Browser Result"
    mock_browser.assert_awaited_once()


@pytest.mark.asyncio
@patch("web_prime_search.engines.google_html._search_via_browser", new_callable=AsyncMock)
@respx.mock
async def test_search_falls_back_to_browser_when_static_page_has_no_results(mock_browser: AsyncMock) -> None:
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text="<html><body>No results</body></html>"))
    mock_browser.return_value = [
        SearchResult(
            title="Browser Result",
            url="https://example.com/browser",
            snippet="Rendered snippet",
            source="google_html",
        )
    ]

    results = await search("query", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].url == "https://example.com/browser"
    mock_browser.assert_awaited_once()


@pytest.mark.asyncio
@patch("web_prime_search.engines.google_html._search_via_browser", new_callable=AsyncMock)
@respx.mock
async def test_search_combines_http_and_browser_errors(mock_browser: AsyncMock) -> None:
    html = '<html><body><noscript><meta content="0;url=/httpservice/retry/enablejs?sei=test" http-equiv="refresh"></noscript></body></html>'
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))
    mock_browser.side_effect = ValueError("browser launch failed")

    with pytest.raises(
        ValueError,
        match="Google HTML search blocked by anti-bot or consent page; browser fallback failed: browser launch failed",
    ):
        await search("query", settings=_SETTINGS)


@pytest.mark.asyncio
@patch("web_prime_search.engines.google_html._search_via_browser", new_callable=AsyncMock)
@respx.mock
async def test_search_returns_empty_when_static_page_has_no_results_and_browser_fails(mock_browser: AsyncMock) -> None:
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text="<html><body>No results</body></html>"))
    mock_browser.side_effect = ValueError("browser unavailable")

    results = await search("query", settings=_SETTINGS)

    assert results == []


def test_build_context_kwargs_respect_stealth_switch() -> None:
    enabled_headers = _build_context_kwargs(_SETTINGS)["extra_http_headers"]
    disabled_headers = _build_context_kwargs(
        Settings(proxy_url="http://127.0.0.1:7897", google_html_stealth=False)
    )["extra_http_headers"]

    assert enabled_headers["Upgrade-Insecure-Requests"] == "1"
    assert "Upgrade-Insecure-Requests" not in disabled_headers
    assert disabled_headers["Accept-Language"] == "zh-CN,zh;q=0.9,en;q=0.8"


def test_resolve_profile_dir_uses_named_cache_location() -> None:
    resolved = _resolve_profile_dir(_SETTINGS)

    assert resolved.name == "google-html-profile"
    assert resolved.parent.name == "web-prime-search"


def test_normalize_cookie_payload_filters_invalid_and_duplicate_entries() -> None:
    cookies = _normalize_cookie_payload(
        [
            {
                "name": "SID",
                "value": "cookie-1",
                "domain": ".google.com",
                "path": "/",
                "expires": 32503680000,
                "httpOnly": True,
                "secure": True,
                "sameSite": "lax",
            },
            {
                "name": "SID",
                "value": "cookie-2",
                "domain": ".google.com",
                "path": "/",
            },
            {
                "name": "OLD",
                "value": "expired",
                "domain": ".google.com",
                "path": "/",
                "expires": 1,
            },
            {
                "name": "EXT",
                "value": "skip",
                "domain": ".example.com",
                "path": "/",
            },
            {
                "name": "",
                "value": "skip",
                "domain": ".google.com",
                "path": "/",
            },
        ]
    )

    assert cookies == [
        {
            "name": "SID",
            "value": "cookie-1",
            "domain": ".google.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "expires": 32503680000.0,
            "sameSite": "Lax",
        }
    ]


@pytest.mark.asyncio
async def test_load_cookies_skips_malformed_cookie_file(tmp_path) -> None:
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text("{broken", encoding="utf-8")
    context = AsyncMock()
    settings = Settings(
        proxy_url="http://127.0.0.1:7897",
        google_html_cookie_file=str(cookie_file),
    )

    await _load_cookies(context, settings)

    context.add_cookies.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_cookies_persists_google_cookies_only(tmp_path) -> None:
    cookie_file = tmp_path / "state" / "cookies.json"
    context = AsyncMock()
    context.cookies.return_value = [
        {
            "name": "SID",
            "value": "cookie-1",
            "domain": ".google.com",
            "path": "/",
            "expires": 32503680000,
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        },
        {
            "name": "EXT",
            "value": "skip",
            "domain": ".example.com",
            "path": "/",
        },
    ]
    settings = Settings(
        proxy_url="http://127.0.0.1:7897",
        google_html_cookie_file=str(cookie_file),
    )

    await _save_cookies(context, settings)

    payload = json.loads(cookie_file.read_text(encoding="utf-8"))
    assert payload == [
        {
            "name": "SID",
            "value": "cookie-1",
            "domain": ".google.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "expires": 32503680000.0,
            "sameSite": "Lax",
        }
    ]


@patch("web_prime_search.engines.google_html._launch_persistent_context", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_open_browser_context_uses_persistent_profile(
    mock_launch_persistent: AsyncMock,
    tmp_path,
) -> None:
    context = AsyncMock()
    profile_dir = tmp_path / "profile"
    settings = Settings(
        proxy_url="http://127.0.0.1:7897",
        google_html_profile_dir=str(profile_dir),
    )
    mock_launch_persistent.return_value = context

    resolved_context, browser = await _open_browser_context(object(), settings)

    assert resolved_context is context
    assert browser is None
    assert profile_dir.exists()
    mock_launch_persistent.assert_awaited_once()


@patch("web_prime_search.engines.google_html._launch_browser", new_callable=AsyncMock)
@patch("web_prime_search.engines.google_html._launch_persistent_context", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_open_browser_context_falls_back_to_ephemeral_when_persistent_profile_fails(
    mock_launch_persistent: AsyncMock,
    mock_launch_browser: AsyncMock,
    tmp_path,
) -> None:
    browser = AsyncMock()
    context = AsyncMock()
    browser.new_context.return_value = context
    mock_launch_browser.return_value = browser
    mock_launch_persistent.side_effect = RuntimeError("profile locked")
    settings = Settings(
        proxy_url="http://127.0.0.1:7897",
        google_html_profile_dir=str(tmp_path / "profile"),
    )

    resolved_context, resolved_browser = await _open_browser_context(object(), settings)

    assert resolved_context is context
    assert resolved_browser is browser
    browser.new_context.assert_awaited_once()