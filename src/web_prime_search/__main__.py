from __future__ import annotations

from web_prime_search.mcp_tool import mcp


def main() -> None:
    """Run the MCP server via stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
