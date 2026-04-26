from __future__ import annotations

import asyncio
import re
from typing import Any

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from web_prime_search.config import Settings, get_settings
from web_prime_search.engines._cli import run_engine_cli
from web_prime_search.models import SearchResult


async def search(
    query: str,
    max_results: int = 10,
    settings: Settings | None = None,
) -> list[SearchResult]:
    if settings is None:
        settings = get_settings()

    proxy = settings.proxy_url if "duckduckgo" in settings.proxy_engines else None
    timeout = _resolve_timeout(settings.engine_timeout_seconds)

    try:
        raw_results = await asyncio.to_thread(
            _run_search,
            query,
            max_results,
            proxy,
            timeout,
            settings,
        )
    except TimeoutException as exc:
        raise ValueError("DuckDuckGo search timed out") from exc
    except RatelimitException as exc:
        raise ValueError("DuckDuckGo search rate limited") from exc
    except DDGSException as exc:
        message = str(exc).strip() or exc.__class__.__name__
        raise ValueError(f"DuckDuckGo search error: {message}") from exc

    return _build_results(raw_results)[:max_results]


def _run_search(
    query: str,
    max_results: int,
    proxy: str | None,
    timeout: int | None,
    settings: Settings,
) -> list[dict[str, Any]]:
    region = settings.duckduckgo_region
    safesearch = settings.duckduckgo_safesearch
    backend_fallback = settings.duckduckgo_backend_fallback
    with DDGS(proxy=proxy, timeout=timeout) as client:
        try:
            return client.text(
                query,
                max_results=max_results,
                backend="duckduckgo",
                region=region,
                safesearch=safesearch,
            )
        except (DDGSException, TimeoutException) as exc:
            if not backend_fallback or isinstance(exc, RatelimitException):
                raise
        return client.text(
            query,
            max_results=max_results,
            backend="lite",
            region=region,
            safesearch=safesearch,
        )


def _build_results(items: list[dict[str, Any]]) -> list[SearchResult]:
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for item in items:
        url = _first_string(item.get("href"), item.get("url"), item.get("link"))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title = _first_string(item.get("title"), item.get("heading"), url) or url
        snippet = _normalize_text(
            _first_string(item.get("body"), item.get("snippet"), item.get("content"), "")
            or ""
        )
        timestamp = _first_string(
            item.get("date"),
            item.get("published"),
            item.get("published_at"),
        )

        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source="duckduckgo",
                timestamp=timestamp,
            )
        )

    return results


def _first_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_text(text: str, *, limit: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _resolve_timeout(timeout_seconds: float) -> int | None:
    if timeout_seconds <= 0:
        return None
    return max(1, int(timeout_seconds))


def main(argv: list[str] | None = None) -> int:
    return run_engine_cli("duckduckgo", search, argv)


if __name__ == "__main__":
    raise SystemExit(main())