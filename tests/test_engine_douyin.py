from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import respx
from httpx import Response

from web_prime_search.config import Settings
from web_prime_search.engines.douyin import search

pytestmark = pytest.mark.asyncio

_RESPONSES_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
_MODEL = "doubao-seed-1-6-250615"
_SETTINGS = Settings(
    volcengine_api_key="ark_test_key",
    volcengine_responses_url=_RESPONSES_URL,
    volcengine_web_search_model=_MODEL,
    proxy_url="http://127.0.0.1:7897",
)


@respx.mock
async def test_search_returns_reference_results():
    route = respx.post(_RESPONSES_URL).mock(
        return_value=Response(
            200,
            json={
                "references": [
                    {
                        "title": "OPC 行业观察",
                        "url": "https://example.com/opc-overview",
                        "summary": "来自火山联网搜索的摘要",
                        "publish_time": "2026-04-02 10:00:00",
                    },
                    {
                        "title": "OPC 热点追踪",
                        "url": "https://example.com/opc-news",
                        "summary": "第二条结果",
                    },
                ]
            },
        )
    )

    results = await search("opc", settings=_SETTINGS)

    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer ark_test_key"
    payload = json.loads(request.content.decode())
    assert payload == {
        "model": _MODEL,
        "stream": False,
        "tools": [{"type": "web_search"}],
        "input": "opc",
    }
    assert len(results) == 2
    assert results[0].source == "douyin"
    assert results[0].title == "OPC 行业观察"
    assert results[0].url == "https://example.com/opc-overview"
    assert results[0].snippet == "来自火山联网搜索的摘要"
    assert results[0].timestamp == "2026-04-02 10:00:00"
    assert results[0].summary is None


@respx.mock
async def test_search_falls_back_to_action_detail_results():
    timestamp = 1712217600
    route = respx.post(_RESPONSES_URL).mock(
        return_value=Response(
            200,
            json={
                "bot_usage": {
                    "action_details": [
                        {
                            "name": "content_plugin",
                            "tool_details": [
                                {
                                    "name": "search",
                                    "output": {
                                        "data": {
                                            "data": {
                                                "results": [
                                                    {
                                                        "title": "OPC 百科",
                                                        "url": "https://example.com/opc-baike",
                                                        "summary": "来自 action_details 的结果",
                                                        "publish_time": timestamp,
                                                    }
                                                ]
                                            }
                                        }
                                    },
                                }
                            ],
                        }
                    ]
                }
            },
        )
    )

    results = await search("opc", settings=_SETTINGS)

    assert route.called
    assert len(results) == 1
    assert results[0].title == "OPC 百科"
    assert results[0].timestamp == datetime.fromtimestamp(
        timestamp, tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")


@respx.mock
async def test_search_parses_output_annotations():
    respx.post(_RESPONSES_URL).mock(
        return_value=Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "以下是热点新闻汇总",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "title": "4月2日新闻早知道",
                                        "url": "https://example.com/news-1",
                                        "summary": "第一条热点摘要",
                                        "publish_time": "2026年04月02日 07:59:00(CST) 星期四",
                                    },
                                    {
                                        "type": "url_citation",
                                        "title": "早啊!新闻来了〔2026.04.02〕",
                                        "url": "https://example.com/news-2",
                                        "summary": "第二条热点摘要",
                                    },
                                ],
                            }
                        ],
                    }
                ]
            },
        )
    )

    results = await search("今天有什么热点新闻？", settings=_SETTINGS)

    assert len(results) == 2
    assert results[0].title == "4月2日新闻早知道"
    assert results[0].url == "https://example.com/news-1"
    assert results[0].snippet == "第一条热点摘要"
    assert results[0].timestamp == "2026年04月02日 07:59:00(CST) 星期四"


@respx.mock
async def test_search_attaches_output_summary_and_shortens_long_snippets():
    respx.post(_RESPONSES_URL).mock(
        return_value=Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "以下是今天的热点：\n1. 国内政策\n2. 国际局势\n3. 民生资讯",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "title": "热点 1",
                                        "url": "https://example.com/hot-1",
                                        "summary": "A" * 500,
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        )
    )

    results = await search("今天有什么热点新闻？", settings=_SETTINGS)

    assert len(results) == 1
    assert results[0].summary == "以下是今天的热点： 1. 国内政策 2. 国际局势 3. 民生资讯"
    assert len(results[0].snippet) == 360
    assert results[0].snippet.endswith("...")


@respx.mock
async def test_search_empty_results_when_no_reference_data():
    respx.post(_RESPONSES_URL).mock(return_value=Response(200, json={}))

    results = await search("opc", settings=_SETTINGS)

    assert results == []


@respx.mock
async def test_search_http_error_surfaces_message():
    respx.post(_RESPONSES_URL).mock(
        return_value=Response(401, json={"error": {"message": "Unauthorized"}})
    )

    with pytest.raises(
        ValueError, match=r"Douyin search error: HTTP 401: Unauthorized"
    ):
        await search("opc", settings=_SETTINGS)


async def test_search_requires_api_key():
    with pytest.raises(ValueError, match="Volcengine API key is not configured"):
        await search(
            "opc",
            settings=Settings(
                volcengine_api_key="",
                volcengine_web_search_model=_MODEL,
            ),
        )


async def test_search_requires_model():
    with pytest.raises(
        ValueError, match="Volcengine web search model is not configured"
    ):
        await search(
            "opc",
            settings=Settings(
                volcengine_api_key="ark_test_key",
                volcengine_web_search_model="",
            ),
        )


async def test_douyin_live_search_prints_results(capsys: pytest.CaptureFixture[str]) -> None:
    if os.environ.get("WPS_RUN_LIVE_DOUYIN_TEST") != "1":
        pytest.skip("Set WPS_RUN_LIVE_DOUYIN_TEST=1 to run the live Douyin search test")

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    src_path = str(repo_root / "src")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else os.pathsep.join([src_path, existing_pythonpath])

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "web_prime_search",
            "search",
            "--query",
            "coding plan",
            "--engines",
            "douyin",
            "--max-results",
            "5",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    with capsys.disabled():
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.stderr.strip():
            print(completed.stderr.strip(), file=sys.stderr)

    assert completed.returncode == 0, completed.stderr

    payload = json.loads(completed.stdout)
    assert payload, "Expected at least one live Douyin search result"


@respx.mock
async def test_search_respects_max_results():
    respx.post(_RESPONSES_URL).mock(
        return_value=Response(
            200,
            json={
                "references": [
                    {
                        "title": f"Result {index}",
                        "url": f"https://example.com/{index}",
                        "summary": f"Snippet {index}",
                    }
                    for index in range(3)
                ]
            },
        )
    )

    results = await search("opc", max_results=2, settings=_SETTINGS)

    assert len(results) == 2
