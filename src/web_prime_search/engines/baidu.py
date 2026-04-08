from __future__ import annotations

import re
from html import unescape

from web_prime_search.config import Settings, get_settings
from web_prime_search.engines._cli import run_engine_cli
from web_prime_search.models import SearchResult
from web_prime_search.proxy import get_http_client

_SEARCH_URL = "https://www.baidu.com/s"


async def search(
    query: str,
    max_results: int = 10,
    settings: Settings | None = None,
) -> list[SearchResult]:
    if settings is None:
        settings = get_settings()

    headers: dict[str, str] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    client = get_http_client("baidu", settings)
    try:
        rn = min(max_results, 50)
        resp = await client.get(
            _SEARCH_URL,
            params={"wd": query, "rn": rn},
            headers=headers,
        )

        if resp.status_code != 200:
            raise ValueError(f"Baidu search error: HTTP {resp.status_code}")

        html = resp.text
        results = _parse_results(html)
        return results[:max_results]
    finally:
        await client.aclose()


def _parse_results(html: str) -> list[SearchResult]:
    results: list[SearchResult] = []

    # Split on each result/c-container div opening tag
    parts = re.split(
        r'<div\s[^>]*class="[^"]*(?:result|c-container)[^"]*"[^>]*>',
        html,
    )

    # First part is before any result div, skip it
    for block in parts[1:]:
        title, url = _extract_title_url(block)
        if not title or not url:
            continue
        snippet = _extract_snippet(block)
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source="baidu",
            )
        )

    return results


def _extract_title_url(block: str) -> tuple[str, str]:
    match = re.search(
        r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        block,
        re.DOTALL,
    )
    if not match:
        return "", ""
    url = match.group(1)
    title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
    title = unescape(title)
    return title, url


def _extract_snippet(block: str) -> str:
    match = re.search(
        r'<div[^>]*class="[^"]*c-abstract[^"]*"[^>]*>(.*?)</div>',
        block,
        re.DOTALL,
    )
    if not match:
        return ""
    snippet = re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return unescape(snippet)


def main(argv: list[str] | None = None) -> int:
    return run_engine_cli("baidu", search, argv)


if __name__ == "__main__":
    raise SystemExit(main())
