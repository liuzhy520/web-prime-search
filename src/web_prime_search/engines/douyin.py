from __future__ import annotations

import json
import re
from urllib.parse import quote, unquote

from web_prime_search.config import Settings, get_settings
from web_prime_search.models import SearchResult
from web_prime_search.proxy import get_http_client

_SEARCH_URL = "https://www.douyin.com/search/{query}?type=video"


async def search(
    query: str,
    max_results: int = 10,
    settings: Settings | None = None,
) -> list[SearchResult]:
    if settings is None:
        settings = get_settings()

    headers: dict[str, str] = {
        "Referer": "https://www.douyin.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if settings.douyin_cookie:
        headers["Cookie"] = settings.douyin_cookie

    client = get_http_client("douyin", settings)
    try:
        url = _SEARCH_URL.format(query=quote(query, safe=""))
        resp = await client.get(url, headers=headers)

        if resp.status_code != 200:
            raise ValueError(f"Douyin search error: HTTP {resp.status_code}")

        html = resp.text
        results = _parse_render_data(html)

        if not results:
            results = _parse_regex_fallback(html)

        return results[:max_results]
    finally:
        await client.aclose()


def _parse_render_data(html: str) -> list[SearchResult]:
    match = re.search(
        r'<script\s+id="RENDER_DATA"\s*[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return []

    try:
        raw = unquote(match.group(1))
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []

    return _extract_from_data(data)


def _extract_from_data(
    data: object,
    *,
    max_depth: int = 25,
    _depth: int = 0,
    _seen_ids: set[int] | None = None,
) -> list[SearchResult]:
    results: list[SearchResult] = []

    if _depth >= max_depth:
        return results

    if _seen_ids is None:
        _seen_ids = set()

    if isinstance(data, dict):
        data_id = id(data)
        if data_id in _seen_ids:
            return results
        _seen_ids.add(data_id)

        # Look for aweme_id which indicates a video entry
        if "aweme_id" in data:
            aweme_id = data["aweme_id"]
            desc = data.get("desc", "")
            title = desc or str(aweme_id)
            results.append(
                SearchResult(
                    title=title,
                    url=f"https://www.douyin.com/video/{aweme_id}",
                    snippet=desc or title,
                    source="douyin",
                )
            )
        else:
            for value in data.values():
                results.extend(
                    _extract_from_data(
                        value,
                        max_depth=max_depth,
                        _depth=_depth + 1,
                        _seen_ids=_seen_ids,
                    )
                )
    elif isinstance(data, list):
        data_id = id(data)
        if data_id in _seen_ids:
            return results
        _seen_ids.add(data_id)

        for item in data:
            results.extend(
                _extract_from_data(
                    item,
                    max_depth=max_depth,
                    _depth=_depth + 1,
                    _seen_ids=_seen_ids,
                )
            )

    return results


def _parse_regex_fallback(html: str) -> list[SearchResult]:
    results: list[SearchResult] = []
    seen: set[str] = set()

    for m in re.finditer(
        r'"aweme_id"\s*:\s*"(\d+)".*?"desc"\s*:\s*"([^"]*)"',
        html,
    ):
        aweme_id, desc = m.group(1), m.group(2)
        if aweme_id in seen:
            continue
        seen.add(aweme_id)
        title = desc or aweme_id
        results.append(
            SearchResult(
                title=title,
                url=f"https://www.douyin.com/video/{aweme_id}",
                snippet=desc or title,
                source="douyin",
            )
        )

    return results
