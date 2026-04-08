from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from typing import Awaitable, Callable, Sequence

from web_prime_search.models import SearchResult


def run_engine_cli(
    engine_name: str,
    search_func: Callable[..., Awaitable[list[SearchResult]]],
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog=f"python -m web_prime_search.engines.{engine_name}",
        description=f"Run a one-shot {engine_name} search and print JSON results.",
    )
    parser.add_argument("query", help="Search query string.")
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum results to return.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        results = asyncio.run(search_func(args.query, max_results=args.max_results))
    except Exception as exc:
        print(f"{engine_name} search failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    return 0