from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from web_prime_search.config import Settings
from web_prime_search.dispatcher import multi_search, resolve_engine_list, search_engine
from web_prime_search.models import SearchResult

pytestmark = pytest.mark.asyncio

_SETTINGS = Settings(
    search_priority=["google", "duckduckgo", "douyin", "baidu", "x", "google_html"],
)


def _make_results(source: str, count: int = 2) -> list[SearchResult]:
    return [
        SearchResult(
            title=f"{source} result {i}",
            url=f"https://{source}.example.com/{i}",
            snippet=f"snippet {i} from {source}",
            source=source,
        )
        for i in range(count)
    ]


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_all_engines_succeed(mock_registry: dict):
    """All engines return results -> aggregated in priority order."""
    mock_registry.get = lambda name: {
        "x": AsyncMock(return_value=_make_results("x")),
        "google": AsyncMock(return_value=_make_results("google")),
        "google_html": AsyncMock(return_value=_make_results("google_html")),
        "douyin": AsyncMock(return_value=_make_results("douyin")),
        "duckduckgo": AsyncMock(return_value=_make_results("duckduckgo")),
        "baidu": AsyncMock(return_value=_make_results("baidu")),
    }.get(name)

    results = await multi_search("test query", settings=_SETTINGS)

    assert len(results) == 12
    # Priority order: google first, then duckduckgo, douyin, baidu, x, google_html
    assert results[0].source == "google"
    assert results[1].source == "google"
    assert results[2].source == "duckduckgo"
    assert results[3].source == "duckduckgo"
    assert results[4].source == "douyin"
    assert results[6].source == "baidu"
    assert results[8].source == "x"
    assert results[10].source == "google_html"


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_one_engine_fails_fallback(mock_registry: dict, caplog):
    """One engine raises -> warning logged, others still return results."""
    mock_registry.get = lambda name: {
        "x": AsyncMock(return_value=_make_results("x")),
        "google": AsyncMock(side_effect=ValueError("API quota exceeded")),
        "google_html": AsyncMock(return_value=_make_results("google_html")),
        "douyin": AsyncMock(return_value=_make_results("douyin")),
        "duckduckgo": AsyncMock(return_value=_make_results("duckduckgo")),
        "baidu": AsyncMock(return_value=_make_results("baidu")),
    }.get(name)

    with caplog.at_level(logging.WARNING):
        results = await multi_search("test query", settings=_SETTINGS)

    assert len(results) == 10  # duckduckgo(2) + douyin(2) + baidu(2) + x(2) + google_html(2), google failed
    sources = [r.source for r in results]
    assert "google" not in sources
    assert "Engine google failed" in caplog.text


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_all_engines_fail(mock_registry: dict, caplog):
    """All engines raise -> returns empty list."""
    failing = AsyncMock(side_effect=RuntimeError("down"))
    mock_registry.get = lambda name: failing if name in {
        "x", "google", "google_html", "douyin", "duckduckgo", "baidu"
    } else None

    with caplog.at_level(logging.WARNING):
        results = await multi_search("test query", settings=_SETTINGS)

    assert results == []
    assert caplog.text.count("failed") == 6


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_custom_engine_list(mock_registry: dict):
    """Custom engine list -> only specified engines called."""
    x_mock = AsyncMock(return_value=_make_results("x"))
    google_mock = AsyncMock(return_value=_make_results("google"))
    google_html_mock = AsyncMock(return_value=_make_results("google_html"))
    douyin_mock = AsyncMock(return_value=_make_results("douyin"))
    duckduckgo_mock = AsyncMock(return_value=_make_results("duckduckgo"))
    baidu_mock = AsyncMock(return_value=_make_results("baidu"))

    mock_registry.get = lambda name: {
        "x": x_mock,
        "google": google_mock,
        "google_html": google_html_mock,
        "douyin": douyin_mock,
        "duckduckgo": duckduckgo_mock,
        "baidu": baidu_mock,
    }.get(name)

    results = await multi_search(
        "test query", engines=["google", "baidu"], settings=_SETTINGS
    )

    assert len(results) == 4
    assert all(r.source in ("google", "baidu") for r in results)
    x_mock.assert_not_awaited()
    douyin_mock.assert_not_awaited()
    google_html_mock.assert_not_awaited()
    duckduckgo_mock.assert_not_awaited()


async def test_unknown_engine_skipped(caplog):
    """Unknown engine name -> skipped with warning, returns empty."""
    with caplog.at_level(logging.WARNING):
        results = await search_engine("nonexistent", "q", 10, _SETTINGS)

    assert results == []
    assert "Unknown engine: nonexistent" in caplog.text


async def test_resolve_engine_list_normalizes_and_deduplicates():
    settings = Settings(search_priority=["google", "duckduckgo", "douyin", "baidu", "x", "google_html"])

    resolved = resolve_engine_list([" Google ", "baidu", "google", "", " X "], settings)

    assert resolved == ["google", "baidu", "x"]

async def test_resolve_engine_list_falls_back_to_default_priority(caplog):
    settings = Settings(search_priority=["google", "duckduckgo", "douyin", "baidu", "x", "google_html"])

    with caplog.at_level(logging.WARNING):
        resolved = resolve_engine_list(["unknown", "   "], settings)

    assert resolved == ["google", "duckduckgo", "douyin", "baidu", "x", "google_html"]
    assert "No valid requested engines supplied" in caplog.text


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_engines_run_concurrently(mock_registry: dict):
    """Engines dispatched via asyncio.gather (concurrent execution)."""
    import asyncio

    call_order: list[str] = []

    async def slow_x(*a, **kw):
        call_order.append("x_start")
        await asyncio.sleep(0.05)
        call_order.append("x_end")
        return _make_results("x", 1)

    async def slow_google(*a, **kw):
        call_order.append("google_start")
        await asyncio.sleep(0.05)
        call_order.append("google_end")
        return _make_results("google", 1)

    mock_registry.get = lambda name: {
        "x": slow_x,
        "google": slow_google,
    }.get(name)

    results = await multi_search(
        "test", engines=["x", "google"], settings=_SETTINGS
    )

    assert len(results) == 2
    # Both should start before either ends (concurrent)
    assert call_order.index("x_start") < call_order.index("google_end")
    assert call_order.index("google_start") < call_order.index("x_end")


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_engine_timeout_returns_empty(mock_registry: dict, caplog):
    import asyncio

    async def slow_engine(*a, **kw):
        await asyncio.sleep(0.05)
        return _make_results("x", 1)

    settings = Settings(
        search_priority=["x"],
        engine_timeout_seconds=0.01,
    )
    mock_registry.get = lambda name: slow_engine if name == "x" else None

    with caplog.at_level(logging.WARNING):
        results = await search_engine("x", "test", 1, settings)

    assert results == []
    assert "Engine x timed out" in caplog.text


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_dispatcher_uses_douyin_specific_timeout(mock_registry: dict):
    captured_timeouts: list[float] = []

    async def fake_engine(*args: Any, **kwargs: Any):
        return _make_results("douyin", 1)

    async def fake_wait_for(coro, timeout):
        captured_timeouts.append(timeout)
        return await coro

    settings = Settings(
        search_priority=["douyin", "x"],
        engine_timeout_seconds=35.0,
        douyin_timeout_seconds=60.0,
    )
    mock_registry.get = lambda name: fake_engine if name in {"douyin", "x"} else None

    with patch("web_prime_search.dispatcher.asyncio.wait_for", side_effect=fake_wait_for):
        await search_engine("douyin", "test", 1, settings)
        await search_engine("x", "test", 1, settings)

    assert captured_timeouts == [60.0, 35.0]
