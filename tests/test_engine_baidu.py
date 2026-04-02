from __future__ import annotations

import pytest
import respx
from httpx import Response

from web_prime_search.config import Settings
from web_prime_search.engines.baidu import search

pytestmark = pytest.mark.asyncio

_SETTINGS = Settings(
    proxy_url="http://127.0.0.1:7897",
)

_SEARCH_URL = "https://www.baidu.com/s"


def _make_result_html(result_id: str, title: str, url: str, snippet: str) -> str:
    return (
        f'<div class="result c-container" id="{result_id}">'
        f'<h3 class="t"><a href="{url}">{title}</a></h3>'
        f'<div class="c-abstract">{snippet}</div>'
        "</div>"
    )


_HTML_TWO_RESULTS = (
    "<html><body>"
    + _make_result_html(
        "1",
        "Python Official Site",
        "http://www.baidu.com/link?url=abc123",
        "Python is a programming language.",
    )
    + _make_result_html(
        "2",
        "Learn Python",
        "http://www.baidu.com/link?url=def456",
        "Comprehensive Python tutorials and guides.",
    )
    + "</body></html>"
)

_HTML_EMPTY = "<html><body><div id='content_left'></div></body></html>"

_HTML_THREE_RESULTS = (
    "<html><body>"
    + _make_result_html(
        "1", "Result A", "http://www.baidu.com/link?url=a", "Snippet A"
    )
    + _make_result_html(
        "2", "Result B", "http://www.baidu.com/link?url=b", "Snippet B"
    )
    + _make_result_html(
        "3", "Result C", "http://www.baidu.com/link?url=c", "Snippet C"
    )
    + "</body></html>"
)


@respx.mock
async def test_search_returns_results():
    respx.get(_SEARCH_URL).mock(
        return_value=Response(200, text=_HTML_TWO_RESULTS)
    )

    results = await search("python", settings=_SETTINGS)

    assert len(results) == 2
    assert results[0].source == "baidu"
    assert results[0].title == "Python Official Site"
    assert results[0].url == "http://www.baidu.com/link?url=abc123"
    assert results[0].snippet == "Python is a programming language."
    assert results[1].title == "Learn Python"
    assert results[1].url == "http://www.baidu.com/link?url=def456"
    assert results[1].snippet == "Comprehensive Python tutorials and guides."


@respx.mock
async def test_search_empty_results():
    respx.get(_SEARCH_URL).mock(
        return_value=Response(200, text=_HTML_EMPTY)
    )

    results = await search("nothing", settings=_SETTINGS)

    assert results == []


@respx.mock
async def test_search_http_error():
    respx.get(_SEARCH_URL).mock(
        return_value=Response(503, text="Service Unavailable")
    )

    with pytest.raises(ValueError, match="Baidu search error: HTTP 503"):
        await search("query", settings=_SETTINGS)


@respx.mock
async def test_search_respects_max_results():
    respx.get(_SEARCH_URL).mock(
        return_value=Response(200, text=_HTML_THREE_RESULTS)
    )

    results = await search("query", max_results=2, settings=_SETTINGS)

    assert len(results) == 2
    assert results[0].title == "Result A"
    assert results[1].title == "Result B"


@respx.mock
async def test_search_html_entities_in_title():
    html = (
        "<html><body>"
        '<div class="result c-container" id="1">'
        '<h3 class="t"><a href="http://www.baidu.com/link?url=x">'
        "C++ &amp; Python &lt;Guide&gt;</a></h3>"
        '<div class="c-abstract">A &quot;great&quot; resource</div>'
        "</div>"
        "</body></html>"
    )
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    results = await search("c++", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].title == "C++ & Python <Guide>"
    assert results[0].snippet == 'A "great" resource'


@respx.mock
async def test_search_missing_snippet():
    html = (
        "<html><body>"
        '<div class="result c-container" id="1">'
        '<h3 class="t"><a href="http://www.baidu.com/link?url=y">No Snippet</a></h3>'
        "</div>"
        "</body></html>"
    )
    respx.get(_SEARCH_URL).mock(return_value=Response(200, text=html))

    results = await search("query", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].title == "No Snippet"
    assert results[0].snippet == ""
