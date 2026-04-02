from __future__ import annotations

import pytest
import respx
from httpx import Response

from web_prime_search.config import Settings
from web_prime_search.engines.google import search

pytestmark = pytest.mark.asyncio

_SETTINGS = Settings(
    google_api_key="test-key",
    google_cx="test-cx",
    proxy_url="http://127.0.0.1:7897",
)

_API_URL = "https://www.googleapis.com/customsearch/v1"


@respx.mock
async def test_search_returns_results():
    respx.get(_API_URL).mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "title": "Example Page",
                        "link": "https://example.com",
                        "snippet": "An example snippet",
                    },
                    {
                        "title": "Another Page",
                        "link": "https://another.com",
                        "snippet": "Another snippet",
                    },
                ],
            },
        )
    )

    results = await search("test query", settings=_SETTINGS)

    assert len(results) == 2
    assert results[0].source == "google"
    assert results[0].title == "Example Page"
    assert results[0].url == "https://example.com"
    assert results[0].snippet == "An example snippet"
    assert results[1].url == "https://another.com"


@respx.mock
async def test_search_empty_results():
    respx.get(_API_URL).mock(
        return_value=Response(200, json={"searchInformation": {"totalResults": "0"}})
    )

    results = await search("nothing here", settings=_SETTINGS)

    assert results == []


@respx.mock
async def test_search_api_error_403():
    respx.get(_API_URL).mock(
        return_value=Response(
            403,
            json={"error": {"message": "Rate Limit Exceeded", "code": 403}},
        )
    )

    with pytest.raises(ValueError, match="Google API quota exceeded"):
        await search("query", settings=_SETTINGS)


async def test_missing_api_key():
    no_key = Settings(google_api_key="", google_cx="test-cx")

    with pytest.raises(ValueError, match="Google API key is not configured"):
        await search("query", settings=no_key)


async def test_missing_cx():
    no_cx = Settings(google_api_key="test-key", google_cx="")

    with pytest.raises(ValueError, match="Google CX is not configured"):
        await search("query", settings=no_cx)


@respx.mock
async def test_search_bad_request_400():
    respx.get(_API_URL).mock(
        return_value=Response(
            400,
            json={"error": {"message": "Invalid Value", "code": 400}},
        )
    )

    with pytest.raises(ValueError, match="Google API error: Invalid Value"):
        await search("query", settings=_SETTINGS)


@respx.mock
async def test_search_server_error():
    respx.get(_API_URL).mock(return_value=Response(500))

    with pytest.raises(ValueError, match="Google API error: HTTP 500"):
        await search("query", settings=_SETTINGS)
