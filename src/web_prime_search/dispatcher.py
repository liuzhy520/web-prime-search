from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, List, Optional

from web_prime_search.config import Settings, get_settings
from web_prime_search.engines import baidu, douyin, google, x
from web_prime_search.models import SearchResult

logger = logging.getLogger(__name__)

# Registry mapping engine name to its search function
ENGINE_REGISTRY: Dict[str, Callable[..., Awaitable[List[SearchResult]]]] = {
    "x": x.search,
    "google": google.search,
    "douyin": douyin.search,
    "baidu": baidu.search,
}


async def search_engine(
    engine_name: str,
    query: str,
    max_results: int,
    settings: Settings,
) -> List[SearchResult]:
    """Search a single engine, returning empty list on failure."""
    func = ENGINE_REGISTRY.get(engine_name)
    if func is None:
        logger.warning("Unknown engine: %s, skipping", engine_name)
        return []
    try:
        return await func(query, max_results=max_results, settings=settings)
    except Exception as exc:
        logger.warning("Engine %s failed: %s", engine_name, exc)
        return []


async def multi_search(
    query: str,
    engines: Optional[List[str]] = None,
    max_results: int = 10,
    settings: Optional[Settings] = None,
) -> List[SearchResult]:
    """Search across multiple engines in priority order with fallback.

    Args:
        query: Search query string.
        engines: Optional list of engine names to use.
            If None, uses settings.search_priority.
        max_results: Max results per engine.
        settings: Optional Settings override.

    Returns:
        Aggregated list of SearchResult from all successful engines,
        ordered by engine priority (highest priority engine results first).
    """
    if settings is None:
        settings = get_settings()

    engine_list = engines if engines is not None else settings.search_priority

    # Run all engines concurrently
    tasks = [
        search_engine(name, query, max_results, settings) for name in engine_list
    ]
    results_per_engine = await asyncio.gather(*tasks)

    # Flatten in priority order
    all_results: List[SearchResult] = []
    for results in results_per_engine:
        all_results.extend(results)

    return all_results
