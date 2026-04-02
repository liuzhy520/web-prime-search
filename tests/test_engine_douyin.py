from __future__ import annotations

from urllib.parse import quote

import pytest
import respx
from httpx import Response

from web_prime_search.config import Settings
from web_prime_search.engines.douyin import _extract_from_data, search

pytestmark = pytest.mark.asyncio

_SETTINGS = Settings(
    douyin_cookie="test_session=abc123",
    proxy_url="http://127.0.0.1:7897",
)

_SEARCH_BASE = "https://www.douyin.com/search/"

# Minimal HTML with a RENDER_DATA script containing two video entries
_RENDER_DATA_JSON = quote(
    '{"app":{"videoData":[{"aweme_id":"111222333","desc":"Funny cat video"},'
    '{"aweme_id":"444555666","desc":"Travel vlog Beijing"}]}}'
)

_HTML_WITH_RENDER_DATA = (
    "<html><body>"
    f'<script id="RENDER_DATA" type="application/json">{_RENDER_DATA_JSON}</script>'
    "</body></html>"
)

_HTML_NO_RENDER_DATA = "<html><body><div>No data here</div></body></html>"

_HTML_WITH_REGEX_FALLBACK = (
    '<html><body><script>'
    '{"aweme_id":"777888999","desc":"Regex fallback video"}'
    "</script></body></html>"
)


@respx.mock
async def test_search_returns_results():
    respx.get(url__startswith=_SEARCH_BASE).mock(
        return_value=Response(200, text=_HTML_WITH_RENDER_DATA)
    )

    results = await search("test query", settings=_SETTINGS)

    assert len(results) == 2
    assert results[0].source == "douyin"
    assert results[0].title == "Funny cat video"
    assert results[0].url == "https://www.douyin.com/video/111222333"
    assert results[0].snippet == "Funny cat video"
    assert results[1].title == "Travel vlog Beijing"
    assert results[1].url == "https://www.douyin.com/video/444555666"


@respx.mock
async def test_search_empty_results():
    empty_data = quote('{"app":{}}')
    html = (
        "<html><body>"
        f'<script id="RENDER_DATA" type="application/json">{empty_data}</script>'
        "</body></html>"
    )
    respx.get(url__startswith=_SEARCH_BASE).mock(
        return_value=Response(200, text=html)
    )

    results = await search("nothing", settings=_SETTINGS)

    assert results == []


@respx.mock
async def test_search_http_error():
    respx.get(url__startswith=_SEARCH_BASE).mock(
        return_value=Response(403, text="Forbidden")
    )

    with pytest.raises(ValueError, match="Douyin search error: HTTP 403"):
        await search("query", settings=_SETTINGS)


@respx.mock
async def test_search_no_render_data_returns_empty():
    respx.get(url__startswith=_SEARCH_BASE).mock(
        return_value=Response(200, text=_HTML_NO_RENDER_DATA)
    )

    results = await search("query", settings=_SETTINGS)

    assert results == []


@respx.mock
async def test_search_regex_fallback():
    respx.get(url__startswith=_SEARCH_BASE).mock(
        return_value=Response(200, text=_HTML_WITH_REGEX_FALLBACK)
    )

    results = await search("query", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].title == "Regex fallback video"
    assert results[0].url == "https://www.douyin.com/video/777888999"
    assert results[0].source == "douyin"


@respx.mock
async def test_search_respects_max_results():
    respx.get(url__startswith=_SEARCH_BASE).mock(
        return_value=Response(200, text=_HTML_WITH_RENDER_DATA)
    )

    results = await search("query", max_results=1, settings=_SETTINGS)

    assert len(results) == 1


@respx.mock
async def test_search_without_cookie():
    settings_no_cookie = Settings(douyin_cookie="", proxy_url="http://127.0.0.1:7897")
    respx.get(url__startswith=_SEARCH_BASE).mock(
        return_value=Response(200, text=_HTML_WITH_RENDER_DATA)
    )

    results = await search("query", settings=settings_no_cookie)

    assert len(results) == 2


async def test_extract_from_data_handles_cyclic_structures():
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic

    results = _extract_from_data(cyclic)

    assert results == []


async def test_extract_from_data_stops_at_depth_limit():
    deep: object = {"aweme_id": "999", "desc": "Too deep"}
    for _ in range(30):
        deep = {"child": deep}

    results = _extract_from_data(deep, max_depth=10)

    assert results == []
