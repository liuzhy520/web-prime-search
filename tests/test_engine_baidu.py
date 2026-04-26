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


@respx.mock
async def test_search_sends_user_agent_header():
    captured = {}

    def capture(request):
        captured["user-agent"] = request.headers.get("user-agent", "")
        return Response(200, text=_HTML_TWO_RESULTS)

    respx.get(_SEARCH_URL).mock(side_effect=capture)

    await search("python", settings=_SETTINGS)

    assert captured["user-agent"] != ""
    assert "Mozilla" in captured["user-agent"]


@respx.mock
async def test_search_sends_referer_header():
    captured = {}

    def capture(request):
        captured["referer"] = request.headers.get("referer", "")
        return Response(200, text=_HTML_TWO_RESULTS)

    respx.get(_SEARCH_URL).mock(side_effect=capture)

    await search("python", settings=_SETTINGS)

    assert captured["referer"] == "https://www.baidu.com/s"


@respx.mock
async def test_search_429_retries_and_succeeds():
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Response(429, text="Too Many Requests")
        return Response(200, text=_HTML_TWO_RESULTS)

    respx.get(_SEARCH_URL).mock(side_effect=side_effect)

    settings = Settings(baidu_retry_attempts=3, baidu_retry_delay=0.0)
    results = await search("python", settings=settings)

    assert len(results) == 2
    assert call_count == 2


@respx.mock
async def test_search_429_exhausted_raises():
    respx.get(_SEARCH_URL).mock(return_value=Response(429, text="Too Many Requests"))

    settings = Settings(baidu_retry_attempts=3, baidu_retry_delay=0.0)
    with pytest.raises(ValueError, match="Baidu search error: HTTP 429"):
        await search("python", settings=settings)


@respx.mock
async def test_search_403_no_retry():
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        return Response(403, text="Forbidden")

    respx.get(_SEARCH_URL).mock(side_effect=side_effect)

    settings = Settings(baidu_retry_attempts=3, baidu_retry_delay=0.0)
    with pytest.raises(ValueError, match="Baidu search error: HTTP 403"):
        await search("python", settings=settings)

    assert call_count == 1
