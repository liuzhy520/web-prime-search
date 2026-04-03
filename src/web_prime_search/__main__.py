from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
import sys
from typing import Sequence

from web_prime_search.dispatcher import SUPPORTED_ENGINES, multi_search
from web_prime_search.mcp_tool import mcp


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_openclaw_config(
    *,
    python_executable: str,
    cwd: str,
    server_name: str,
) -> dict[str, object]:
    return {
        "mcpServers": {
            server_name: {
                "command": python_executable,
                "args": ["-m", "web_prime_search", "serve"],
                "cwd": cwd,
                "env": {"PYTHONUNBUFFERED": "1"},
            }
        }
    }


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

    openclaw_parser = subparsers.add_parser(
        "openclaw-config",
        help="Print a local MCP config snippet for OpenClaw.",
    )
    openclaw_parser.add_argument(
        "--python",
        dest="python_executable",
        default=sys.executable,
        help="Python executable that OpenClaw should launch.",
    )
    openclaw_parser.add_argument(
        "--cwd",
        default=str(_repository_root()),
        help="Working directory for the MCP server; keep this at the repo root unless you know otherwise.",
    )
    openclaw_parser.add_argument(
        "--server-name",
        default=mcp.name,
        help="Server name to register inside OpenClaw.",
    )
    openclaw_parser.set_defaults(command="openclaw-config")

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
        "--engine",
        dest="engines",
        help=(
            "Comma-separated engines to use for this request. Supported values: "
            + ", ".join(SUPPORTED_ENGINES)
            + ". Alias: google_api -> google."
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

    if args.command == "openclaw-config":
        payload = _build_openclaw_config(
            python_executable=args.python_executable,
            cwd=args.cwd,
            server_name=args.server_name,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "search":
        payload = asyncio.run(_run_search_command(args))
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
