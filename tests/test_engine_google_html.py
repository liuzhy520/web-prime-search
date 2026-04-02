from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from web_prime_search.config import Settings
from web_prime_search.engines.google_html import search
from web_prime_search.models import SearchResult

pytestmark = pytest.mark.asyncio

_SEARCH_URL = "https://www.google.com/search"
_SETTINGS = Settings(proxy_url="http://127.0.0.1:7897")


def _result_block(href: str, title: str, snippet: str) -> str:
    return (
        '<div class="MjjYud">'
        f'<a href="{href}"><h3>{title}</h3></a>'
        f'<div class="VwiC3b">{snippet}</div>'
        "</div>"
    )


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


@respx.mock
async def test_search_respects_max_results() -> None:
    html = "".join(
        _result_block(f"https://example.com/{index}", f"Result {index}", f"Snippet {index}")
        for index in range(3)
    )
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    results = await search("test query", max_results=2, settings=_SETTINGS)

    assert len(results) == 2


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


@respx.mock
async def test_search_empty_results() -> None:
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text="<html><body>No results</body></html>"))

    results = await search("nothing", settings=_SETTINGS)

    assert results == []


@respx.mock
async def test_search_http_error() -> None:
    respx.get(_SEARCH_URL).mock(return_value=Response(503))

    with pytest.raises(ValueError, match="Google HTML search error: HTTP 503"):
        await search("query", settings=_SETTINGS)


@respx.mock
async def test_search_detects_blocked_page() -> None:
    html = "<html><body>Our systems have detected unusual traffic from your computer network.</body></html>"
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    with pytest.raises(
        ValueError,
        match="Google HTML search blocked by anti-bot or consent page",
    ):
        await search("query", settings=_SETTINGS)


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


@patch("web_prime_search.engines.google_html._search_via_browser", new_callable=AsyncMock)
@respx.mock
async def test_search_returns_empty_when_static_page_has_no_results_and_browser_fails(mock_browser: AsyncMock) -> None:
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text="<html><body>No results</body></html>"))
    mock_browser.side_effect = ValueError("browser unavailable")

    results = await search("query", settings=_SETTINGS)

    assert results == []