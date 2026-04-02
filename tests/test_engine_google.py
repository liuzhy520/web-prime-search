from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from web_prime_search.config import Settings
from web_prime_search.engines.google import (
    _build_browser_settings,
    _build_search_url,
    _build_results_from_dom_items,
    _run_browser_search,
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
