from __future__ import annotations

from web_prime_search.config import Settings, get_settings
from web_prime_search.engines._cli import run_engine_cli
from web_prime_search.models import SearchResult
from web_prime_search.proxy import get_http_client

_API_URL = "https://api.twitter.com/2/tweets/search/recent"


async def search(
    query: str,
    max_results: int = 10,
    settings: Settings | None = None,
) -> list[SearchResult]:
    if settings is None:
        settings = get_settings()

    client = get_http_client("x", settings)
    try:
        resp = await client.get(
            _API_URL,
            headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
            params={
                "query": query,
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,author_id,text",
            },
        )
    except Exception:
        await client.aclose()
        raise

    try:
        if resp.status_code == 401:
            raise ValueError("X API auth failed")
        if resp.status_code == 429:
            raise ValueError("X API rate limited")
        if resp.status_code != 200:
            raise ValueError(f"X API error: HTTP {resp.status_code}")

        data = resp.json()
        tweets = data.get("data") or []

        results: list[SearchResult] = []
        for tweet in tweets:
            text = tweet.get("text", "")
            title = text[:80] + "…" if len(text) > 80 else text
            results.append(
                SearchResult(
                    title=title,
                    url=f"https://x.com/i/status/{tweet['id']}",
                    snippet=text,
                    source="x",
                    timestamp=tweet.get("created_at"),
                )
            )
        return results
    finally:
        await client.aclose()


def main(argv: list[str] | None = None) -> int:
    return run_engine_cli("x", search, argv)


if __name__ == "__main__":
    raise SystemExit(main())
