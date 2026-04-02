from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from typing import Sequence

from web_prime_search.dispatcher import SUPPORTED_ENGINES, multi_search
from web_prime_search.mcp_tool import mcp


def _parse_engine_list(raw_value: str | None) -> list[str] | None:
    if raw_value is None:
        return None
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="web-prime-search",
        description="Search the web via MCP or run a one-shot multi-engine search.",
    )
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser(
        "serve",
        help="Run the MCP server over stdio.",
    )
    serve_parser.set_defaults(command="serve")

    search_parser = subparsers.add_parser(
        "search",
        help="Run a one-shot search and print JSON results.",
    )
    search_parser.add_argument(
        "--query",
        required=True,
        help="Search query string.",
    )
    search_parser.add_argument(
        "--engines",
        help=(
            "Comma-separated engines to use for this request. Supported values: "
            + ", ".join(SUPPORTED_ENGINES)
        ),
    )
    search_parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum results per engine.",
    )
    return parser


async def _run_search_command(args: argparse.Namespace) -> list[dict[str, object]]:
    results = await multi_search(
        query=args.query,
        engines=_parse_engine_list(args.engines),
        max_results=args.max_results,
    )
    return [asdict(result) for result in results]


def main(argv: Sequence[str] | None = None) -> None:
    """Run the MCP server or a one-shot CLI search."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command in (None, "serve"):
        mcp.run(transport="stdio")
        return

    if args.command == "search":
        payload = asyncio.run(_run_search_command(args))
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
