from __future__ import annotations

import pytest
import respx
from httpx import Response

from web_prime_search.config import Settings
from web_prime_search.engines.x import search

pytestmark = pytest.mark.asyncio

_SETTINGS = Settings(x_bearer_token="test-token", proxy_url="http://127.0.0.1:7897")

_API_URL = "https://api.twitter.com/2/tweets/search/recent"


@respx.mock
async def test_search_returns_results():
    respx.get(_API_URL).mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": "111",
                        "text": "Hello world from X",
                        "created_at": "2025-01-01T00:00:00.000Z",
                        "author_id": "42",
                    },
                    {
                        "id": "222",
                        "text": "Second tweet",
                        "created_at": "2025-01-02T00:00:00.000Z",
                        "author_id": "43",
                    },
                ],
                "meta": {"result_count": 2},
            },
        )
    )

    results = await search("test query", settings=_SETTINGS)

    assert len(results) == 2
    assert results[0].source == "x"
    assert results[0].url == "https://x.com/i/status/111"
    assert results[0].snippet == "Hello world from X"
    assert results[0].timestamp == "2025-01-01T00:00:00.000Z"
    assert results[1].url == "https://x.com/i/status/222"


@respx.mock
async def test_search_empty_results():
    respx.get(_API_URL).mock(
        return_value=Response(200, json={"meta": {"result_count": 0}})
    )

    results = await search("nothing here", settings=_SETTINGS)

    assert results == []


@respx.mock
async def test_search_auth_error():
    respx.get(_API_URL).mock(
        return_value=Response(401, json={"detail": "Unauthorized"})
    )

    with pytest.raises(ValueError, match="X API auth failed"):
        await search("query", settings=_SETTINGS)


@respx.mock
async def test_search_rate_limited():
    respx.get(_API_URL).mock(
        return_value=Response(429, json={"detail": "Too Many Requests"})
    )

    with pytest.raises(ValueError, match="X API rate limited"):
        await search("query", settings=_SETTINGS)
