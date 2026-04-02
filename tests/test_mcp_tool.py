from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from web_prime_search.mcp_tool import mcp, web_search
from web_prime_search.models import SearchResult


def test_mcp_server_name():
    """MCP server has the expected name."""
    assert mcp.name == "web-prime-search"


def test_tool_registered():
    """web_search tool is registered in the MCP server."""
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "web_search" in tool_names


@patch("web_prime_search.mcp_tool.multi_search")
@pytest.mark.asyncio
async def test_web_search_calls_dispatcher(mock_multi: AsyncMock):
    """web_search delegates to multi_search and formats output."""
    mock_multi.return_value = [
        SearchResult(
            title="Result 1",
            url="https://example.com/1",
            snippet="snippet 1",
            source="google",
            timestamp="2024-01-01",
        ),
        SearchResult(
            title="Result 2",
            url="https://example.com/2",
            snippet="snippet 2",
            source="baidu",
        ),
    ]

    result = await web_search(query="test", engines=["google", "baidu"], max_results=5)

    mock_multi.assert_awaited_once_with(
        query="test", engines=["google", "baidu"], max_results=5
    )
    assert len(result) == 2
    assert result[0] == {
        "title": "Result 1",
        "url": "https://example.com/1",
        "snippet": "snippet 1",
        "source": "google",
        "timestamp": "2024-01-01",
    }
    assert result[1]["source"] == "baidu"
    assert result[1]["timestamp"] is None


@patch("web_prime_search.mcp_tool.multi_search")
@pytest.mark.asyncio
async def test_web_search_defaults(mock_multi: AsyncMock):
    """web_search passes default arguments when optional params omitted."""
    mock_multi.return_value = []

    result = await web_search(query="hello")

    mock_multi.assert_awaited_once_with(query="hello", engines=None, max_results=10)
    assert result == []
