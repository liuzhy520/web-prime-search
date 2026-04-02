from __future__ import annotations

from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from web_prime_search.dispatcher import multi_search

mcp = FastMCP(
    "web-prime-search",
    instructions="Multi-engine search tool with priority routing across Google, Douyin, Baidu, and X",
)


@mcp.tool()
async def web_search(
    query: str,
    engines: Optional[List[str]] = None,
    max_results: int = 10,
) -> list[dict]:
    """Search across multiple engines with priority-based routing.

    Searches are routed through a local Clash proxy for engines that need it (X, Google)
    and directly for domestic engines (Douyin, Baidu).

    Args:
        query: The search query string
        engines: Optional list of engines to use for this request.
            Supported values: google, douyin, baidu, x.
            Example: ["x", "baidu"]. Invalid names are ignored.
            If no valid engine remains, falls back to the configured default priority.
        max_results: Maximum results per engine (default 10)

    Returns:
        List of search results with title, url, snippet, source, and optional timestamp.
        Results are grouped by the resolved engine order.
    """
    results = await multi_search(query=query, engines=engines, max_results=max_results)
    return [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "source": r.source,
            "timestamp": r.timestamp,
        }
        for r in results
    ]
