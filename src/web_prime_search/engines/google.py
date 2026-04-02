from __future__ import annotations

from web_prime_search.config import Settings, get_settings
from web_prime_search.models import SearchResult
from web_prime_search.proxy import get_http_client

_API_URL = "https://www.googleapis.com/customsearch/v1"


async def search(
    query: str,
    max_results: int = 10,
    settings: Settings | None = None,
) -> list[SearchResult]:
    if settings is None:
        settings = get_settings()

    if not settings.google_api_key:
        raise ValueError("Google API key is not configured")
    if not settings.google_cx:
        raise ValueError("Google CX is not configured")

    client = get_http_client("google", settings)
    try:
        results: list[SearchResult] = []
        start = 1
        remaining = max_results

        while remaining > 0:
            num = min(remaining, 10)
            resp = await client.get(
                _API_URL,
                params={
                    "key": settings.google_api_key,
                    "cx": settings.google_cx,
                    "q": query,
                    "num": num,
                    "start": start,
                },
            )

            if resp.status_code == 403:
                raise ValueError("Google API quota exceeded")
            if resp.status_code == 400:
                data = resp.json()
                msg = data.get("error", {}).get("message", "Bad request")
                raise ValueError(f"Google API error: {msg}")
            if resp.status_code != 200:
                raise ValueError(f"Google API error: HTTP {resp.status_code}")

            data = resp.json()
            items = data.get("items") or []

            for item in items:
                results.append(
                    SearchResult(
                        title=item["title"],
                        url=item["link"],
                        snippet=item.get("snippet", ""),
                        source="google",
                    )
                )

            if len(items) < num:
                break

            start += num
            remaining -= num

        return results
    finally:
        await client.aclose()
