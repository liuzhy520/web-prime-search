"""Convenience launcher at repo root.

Canonical implementation lives at openclaw/web-prime-search/launch.py.
This file is a thin shim that delegates to it via exec so that Hermes
and other agents that search relative to the repo root can invoke the
launcher without knowing the nested path.

Usage (from repo root):
    python3 launch.py serve
    python3 launch.py search --query "..." --engines duckduckgo
"""
from __future__ import annotations

from pathlib import Path

_canonical = (
    Path(__file__).resolve().parent
    / "openclaw"
    / "web-prime-search"
    / "launch.py"
)
exec(compile(_canonical.read_text(encoding="utf-8"), str(_canonical), "exec"))  # noqa: S102
