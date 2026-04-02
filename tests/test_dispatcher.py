from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from web_prime_search.config import Settings
from web_prime_search.dispatcher import multi_search, search_engine
from web_prime_search.models import SearchResult

pytestmark = pytest.mark.asyncio

_SETTINGS = Settings(
    search_priority=["x", "google", "douyin", "baidu"],
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
        "douyin": AsyncMock(return_value=_make_results("douyin")),
        "baidu": AsyncMock(return_value=_make_results("baidu")),
    }.get(name)

    results = await multi_search("test query", settings=_SETTINGS)

    assert len(results) == 8
    # Priority order: x first, then google, douyin, baidu
    assert results[0].source == "x"
    assert results[1].source == "x"
    assert results[2].source == "google"
    assert results[3].source == "google"
    assert results[4].source == "douyin"
    assert results[6].source == "baidu"


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_one_engine_fails_fallback(mock_registry: dict, caplog):
    """One engine raises -> warning logged, others still return results."""
    mock_registry.get = lambda name: {
        "x": AsyncMock(return_value=_make_results("x")),
        "google": AsyncMock(side_effect=ValueError("API quota exceeded")),
        "douyin": AsyncMock(return_value=_make_results("douyin")),
        "baidu": AsyncMock(return_value=_make_results("baidu")),
    }.get(name)

    with caplog.at_level(logging.WARNING):
        results = await multi_search("test query", settings=_SETTINGS)

    assert len(results) == 6  # x(2) + douyin(2) + baidu(2), google failed
    sources = [r.source for r in results]
    assert "google" not in sources
    assert "Engine google failed" in caplog.text


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_all_engines_fail(mock_registry: dict, caplog):
    """All engines raise -> returns empty list."""
    failing = AsyncMock(side_effect=RuntimeError("down"))
    mock_registry.get = lambda name: failing if name in {
        "x", "google", "douyin", "baidu"
    } else None

    with caplog.at_level(logging.WARNING):
        results = await multi_search("test query", settings=_SETTINGS)

    assert results == []
    assert caplog.text.count("failed") == 4


@patch("web_prime_search.dispatcher.ENGINE_REGISTRY")
async def test_custom_engine_list(mock_registry: dict):
    """Custom engine list -> only specified engines called."""
    x_mock = AsyncMock(return_value=_make_results("x"))
    google_mock = AsyncMock(return_value=_make_results("google"))
    douyin_mock = AsyncMock(return_value=_make_results("douyin"))
    baidu_mock = AsyncMock(return_value=_make_results("baidu"))

    mock_registry.get = lambda name: {
        "x": x_mock,
        "google": google_mock,
        "douyin": douyin_mock,
        "baidu": baidu_mock,
    }.get(name)

    results = await multi_search(
        "test query", engines=["google", "baidu"], settings=_SETTINGS
    )

    assert len(results) == 4
    assert all(r.source in ("google", "baidu") for r in results)
    x_mock.assert_not_awaited()
    douyin_mock.assert_not_awaited()


async def test_unknown_engine_skipped(caplog):
    """Unknown engine name -> skipped with warning, returns empty."""
    with caplog.at_level(logging.WARNING):
        results = await search_engine("nonexistent", "q", 10, _SETTINGS)

    assert results == []
    assert "Unknown engine: nonexistent" in caplog.text


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
