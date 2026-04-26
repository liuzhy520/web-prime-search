from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from web_prime_search.config import Settings
from web_prime_search.engines.duckduckgo import search

pytestmark = pytest.mark.asyncio


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_returns_results(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.return_value = [
        {
            "title": "Result 1",
            "href": "https://example.com/1",
            "body": "Snippet 1",
            "date": "2026-04-02T12:00:00Z",
        },
        {
            "title": "Result 2",
            "url": "https://example.com/2",
            "snippet": "Snippet 2",
        },
    ]
    mock_ddgs.return_value.__enter__.return_value = instance

    settings = Settings(proxy_url="http://127.0.0.1:7897", proxy_engines=["duckduckgo"])
    results = await search("test query", settings=settings)

    mock_ddgs.assert_called_once_with(proxy="http://127.0.0.1:7897", timeout=35)
    instance.text.assert_called_once_with("test query", max_results=10, backend="duckduckgo", region="wt-wt", safesearch="moderate")
    assert len(results) == 2
    assert results[0].source == "duckduckgo"
    assert results[0].url == "https://example.com/1"
    assert results[0].snippet == "Snippet 1"
    assert results[0].timestamp == "2026-04-02T12:00:00Z"
    assert results[1].url == "https://example.com/2"


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_without_proxy(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.return_value = []
    mock_ddgs.return_value.__enter__.return_value = instance

    settings = Settings(proxy_engines=["google", "x"])
    await search("test query", settings=settings)

    mock_ddgs.assert_called_once_with(proxy=None, timeout=35)


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_falls_back_to_url_for_title(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.return_value = [
        {
            "href": "https://example.com/no-title",
            "body": "Snippet without title",
        }
    ]
    mock_ddgs.return_value.__enter__.return_value = instance

    results = await search("test query")

    assert len(results) == 1
    assert results[0].title == "https://example.com/no-title"


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_ignores_items_without_url(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.return_value = [
        {"title": "Missing URL", "body": "no link"},
        {"title": "Good", "href": "https://example.com/good", "body": "ok"},
    ]
    mock_ddgs.return_value.__enter__.return_value = instance

    results = await search("test query")

    assert len(results) == 1
    assert results[0].url == "https://example.com/good"


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_respects_max_results(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.return_value = [
        {"title": f"Result {index}", "href": f"https://example.com/{index}", "body": "x"}
        for index in range(3)
    ]
    mock_ddgs.return_value.__enter__.return_value = instance

    results = await search("test query", max_results=2)

    assert len(results) == 2
    instance.text.assert_called_once_with("test query", max_results=2, backend="duckduckgo", region="wt-wt", safesearch="moderate")


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_normalizes_ddgs_timeout(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.side_effect = TimeoutException("timed out")
    mock_ddgs.return_value.__enter__.return_value = instance

    with pytest.raises(ValueError, match="DuckDuckGo search timed out"):
        await search("test query")


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_normalizes_ddgs_rate_limit(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.side_effect = RatelimitException("rate limit")
    mock_ddgs.return_value.__enter__.return_value = instance

    with pytest.raises(ValueError, match="DuckDuckGo search rate limited"):
        await search("test query")


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_normalizes_generic_ddgs_errors(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.side_effect = DDGSException("backend unavailable")
    mock_ddgs.return_value.__enter__.return_value = instance

    with pytest.raises(ValueError, match="DuckDuckGo search error: backend unavailable"):
        await search("test query")


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_passes_region(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.return_value = []
    mock_ddgs.return_value.__enter__.return_value = instance

    settings = Settings(duckduckgo_region="us-en")
    await search("test query", settings=settings)

    call_kwargs = instance.text.call_args[1]
    assert call_kwargs["region"] == "us-en"


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_passes_safesearch(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.return_value = []
    mock_ddgs.return_value.__enter__.return_value = instance

    settings = Settings(duckduckgo_safesearch="off")
    await search("test query", settings=settings)

    call_kwargs = instance.text.call_args[1]
    assert call_kwargs["safesearch"] == "off"


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_backend_fallback_on_ddgs_error(mock_ddgs) -> None:
    instance = MagicMock()
    fallback_result = [
        {"title": "Fallback", "href": "https://example.com/fallback", "body": "ok"}
    ]
    instance.text.side_effect = [DDGSException("backend down"), fallback_result]
    mock_ddgs.return_value.__enter__.return_value = instance

    settings = Settings(duckduckgo_backend_fallback=True)
    results = await search("test query", settings=settings)

    assert len(results) == 1
    assert results[0].url == "https://example.com/fallback"
    assert instance.text.call_count == 2
    assert instance.text.call_args_list[1][1]["backend"] == "lite"


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_no_fallback_on_rate_limit(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.side_effect = RatelimitException("rate limited")
    mock_ddgs.return_value.__enter__.return_value = instance

    settings = Settings(duckduckgo_backend_fallback=True)
    with pytest.raises(ValueError, match="DuckDuckGo search rate limited"):
        await search("test query", settings=settings)

    assert instance.text.call_count == 1


@patch("web_prime_search.engines.duckduckgo.DDGS")
async def test_search_fallback_disabled(mock_ddgs) -> None:
    instance = MagicMock()
    instance.text.side_effect = DDGSException("backend down")
    mock_ddgs.return_value.__enter__.return_value = instance

    settings = Settings(duckduckgo_backend_fallback=False)
    with pytest.raises(ValueError, match="DuckDuckGo search error: backend down"):
        await search("test query", settings=settings)

    assert instance.text.call_count == 1