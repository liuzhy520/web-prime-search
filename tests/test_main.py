from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from web_prime_search.__main__ import main
from web_prime_search.models import SearchResult


@patch("web_prime_search.__main__.mcp.run")
def test_main_defaults_to_mcp_server(mock_run) -> None:
    main([])

    mock_run.assert_called_once_with(transport="stdio")


@patch("web_prime_search.__main__.mcp.run")
def test_main_serve_runs_mcp_server(mock_run) -> None:
    main(["serve"])

    mock_run.assert_called_once_with(transport="stdio")


@patch("web_prime_search.__main__.multi_search", new_callable=AsyncMock)
def test_main_search_prints_json(mock_multi_search, capsys) -> None:
    mock_multi_search.return_value = [
        SearchResult(
            title="Result 1",
            url="https://example.com/1",
            snippet="snippet 1",
            source="x",
            timestamp="2026-04-02T00:00:00Z",
            summary="top summary",
        )
    ]

    main(["search", "--query", "opc", "--engines", "X, baidu, unknown", "--max-results", "3"])

    mock_multi_search.assert_awaited_once_with(
        query="opc",
        engines=["X", "baidu", "unknown"],
        max_results=3,
    )
    output = capsys.readouterr().out
    assert json.loads(output) == [
        {
            "title": "Result 1",
            "url": "https://example.com/1",
            "snippet": "snippet 1",
            "source": "x",
            "timestamp": "2026-04-02T00:00:00Z",
            "summary": "top summary",
        }
    ]

@patch("web_prime_search.__main__.multi_search", new_callable=AsyncMock)
def test_main_search_accepts_single_engine_alias_option(mock_multi_search, capsys) -> None:
    mock_multi_search.return_value = []

    main(["search", "--query", "geo", "--engine", "google_api", "--max-results", "2"])

    mock_multi_search.assert_awaited_once_with(
        query="geo",
        engines=["google_api"],
        max_results=2,
    )
    assert json.loads(capsys.readouterr().out) == []