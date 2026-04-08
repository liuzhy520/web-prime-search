from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from web_prime_search.engines._cli import run_engine_cli
from web_prime_search.engines.google import main as google_main
from web_prime_search.models import SearchResult


@patch("web_prime_search.engines.google.search", new_callable=AsyncMock)
def test_google_module_main_prints_json(mock_search, capsys) -> None:
    mock_search.return_value = [
        SearchResult(
            title="Result 1",
            url="https://example.com/1",
            snippet="snippet 1",
            source="google",
        )
    ]

    exit_code = google_main(["coding plan", "--max-results", "2"])

    assert exit_code == 0
    mock_search.assert_awaited_once_with("coding plan", max_results=2)
    assert json.loads(capsys.readouterr().out) == [
        {
            "title": "Result 1",
            "url": "https://example.com/1",
            "snippet": "snippet 1",
            "source": "google",
            "timestamp": None,
            "summary": None,
        }
    ]


@patch("web_prime_search.engines._cli.asyncio.run")
def test_run_engine_cli_prints_error_and_returns_nonzero(mock_asyncio_run, capsys) -> None:
    mock_asyncio_run.side_effect = ValueError("Google CX is not configured")

    exit_code = run_engine_cli("google", AsyncMock(), ["coding plan"])

    assert exit_code == 1
    assert capsys.readouterr().err.strip() == (
        "google search failed: Google CX is not configured"
    )