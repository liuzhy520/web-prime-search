from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

from web_prime_search.config import Settings, get_settings
from web_prime_search.engines import baidu, douyin, duckduckgo, google, google_html, x
from web_prime_search.models import SearchResult

logger = logging.getLogger(__name__)
ENGINE_ALIASES: Dict[str, str] = {
    "google_api": "google",
}

# Registry mapping engine name to its search function
ENGINE_REGISTRY: Dict[str, Callable[..., Awaitable[List[SearchResult]]]] = {
    "x": x.search,
    "google": google.search,
    "google_html": google_html.search,
    "douyin": douyin.search,
    "duckduckgo": duckduckgo.search,
    "baidu": baidu.search,
}

SUPPORTED_ENGINES: Tuple[str, ...] = tuple(ENGINE_REGISTRY.keys())


def _canonicalize_engine_name(name: str) -> str:
    candidate = name.strip().lower()
    return ENGINE_ALIASES.get(candidate, candidate)

def _normalize_engine_names(engine_names: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()
    for name in engine_names:
        candidate = _canonicalize_engine_name(name)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _partition_known_engines(engine_names: Iterable[str]) -> tuple[List[str], List[str]]:
    valid: List[str] = []
    invalid: List[str] = []
    for name in engine_names:
        if ENGINE_REGISTRY.get(name) is not None:
            valid.append(name)
        else:
            invalid.append(name)
    return valid, invalid


def resolve_engine_list(
    engines: Optional[List[str]],
    settings: Settings,
) -> List[str]:
    """Resolve requested engines to a valid execution order.

    Request-specific engines take precedence when at least one valid engine is
    supplied. Invalid entries are ignored. If the requested list is empty or has
    no valid engines, the configured default priority is used instead.
    """
    default_candidates = _normalize_engine_names(settings.search_priority)
    default_engines, invalid_defaults = _partition_known_engines(default_candidates)
    if invalid_defaults:
        logger.warning(
            "Ignoring invalid engines in WPS_SEARCH_PRIORITY: %s",
            ", ".join(invalid_defaults),
        )
    if not default_engines:
        logger.warning(
            "Configured search priority has no valid engines; using built-in defaults"
        )
        default_engines = list(SUPPORTED_ENGINES)

    if engines is None:
        return default_engines

    requested_candidates = _normalize_engine_names(engines)
    requested_engines, invalid_requested = _partition_known_engines(requested_candidates)
    if invalid_requested:
        logger.warning(
            "Ignoring invalid requested engines: %s",
            ", ".join(invalid_requested),
        )
    if requested_engines:
        return requested_engines

    logger.warning(
        "No valid requested engines supplied; falling back to default priority"
    )
    return default_engines


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
        coroutine = func(query, max_results=max_results, settings=settings)
        if settings.engine_timeout_seconds > 0:
            return await asyncio.wait_for(
                coroutine,
                timeout=settings.engine_timeout_seconds,
            )
        return await coroutine
    except asyncio.TimeoutError:
        logger.warning(
            "Engine %s timed out after %.1f seconds",
            engine_name,
            settings.engine_timeout_seconds,
        )
        return []
    except Exception as exc:
        error_message = str(exc).strip() or exc.__class__.__name__
        logger.warning("Engine %s failed: %s", engine_name, error_message)
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

    engine_list = resolve_engine_list(engines, settings)

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
