"""Network and configuration diagnostics for web-prime-search.

Run from any directory:
    python scripts/diagnose_network.py

The script loads settings via get_settings(), reports which .env was found,
checks for empty credentials that look misconfigured, then probes each engine's
target host to verify proxy vs direct routing.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure the installed package (or editable src/) is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx

from web_prime_search.config import _resolve_env_files, get_settings

# --- pretty helpers -------------------------------------------------------

_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


def _ok(msg: str) -> str:
    return f"{_GREEN}✓{_RESET} {msg}"


def _fail(msg: str) -> str:
    return f"{_RED}✗{_RESET} {msg}"


def _warn(msg: str) -> str:
    return f"{_YELLOW}!{_RESET} {msg}"


def _header(msg: str) -> None:
    print(f"\n{_BOLD}{msg}{_RESET}")
    print("─" * 60)


def _redact(value: str, show: int = 6) -> str:
    if not value:
        return "(empty)"
    if len(value) <= show * 2:
        return "***"
    return value[:show] + "…" + value[-show:]


# --- config section -------------------------------------------------------

def _print_config() -> None:
    _header("1. Configuration")

    env_files = _resolve_env_files()
    if env_files:
        print(_ok(f".env loaded from: {env_files[0]}"))
    else:
        wps_env = os.environ.get("WPS_ENV_FILE", "")
        if wps_env:
            print(_fail(f"WPS_ENV_FILE is set to '{wps_env}' but file does not exist"))
        else:
            print(_warn("No .env file found (searched cwd→/ and package dir→/)"))

    s = get_settings()

    rows = [
        ("WPS_PROXY_URL",                  s.proxy_url,                 True),
        ("WPS_PROXY_ENGINES",              str(s.proxy_engines),         False),
        ("WPS_DIRECT_ENGINES",             str(s.direct_engines),        False),
        ("WPS_GOOGLE_CX",                  s.google_cx,                  True),
        ("WPS_X_BEARER_TOKEN",             s.x_bearer_token,             True),
        ("WPS_VOLCENGINE_API_KEY",         s.volcengine_api_key,         True),
        ("WPS_VOLCENGINE_WEB_SEARCH_MODEL",s.volcengine_web_search_model,False),
        ("WPS_ENGINE_TIMEOUT_SECONDS",     str(s.engine_timeout_seconds),False),
    ]

    issues: list[str] = []
    for name, value, sensitive in rows:
        display = _redact(value) if sensitive else value
        status = _ok(f"{name} = {display}") if value else _warn(f"{name} = (empty)")
        print(f"  {status}")

    # Specific required-key checks
    if not s.google_cx:
        issues.append("WPS_GOOGLE_CX is required for google engine")
    if not s.x_bearer_token:
        issues.append("WPS_X_BEARER_TOKEN is required for x engine")
    if not s.volcengine_api_key:
        issues.append("WPS_VOLCENGINE_API_KEY is required for douyin engine")
    if not s.volcengine_web_search_model:
        issues.append("WPS_VOLCENGINE_WEB_SEARCH_MODEL is required for douyin engine")

    if issues:
        print()
        for issue in issues:
            print(f"  {_warn(issue)}")

    return s


# --- network probe --------------------------------------------------------

_PROBE_TIMEOUT = 10.0

# (engine, url, use_proxy, description)
_PROBES: list[tuple[str, str, bool, str]] = [
    ("google",      "https://cse.google.com/",                  True,  "Google CSE (needs proxy)"),
    ("duckduckgo",  "https://duckduckgo.com/",                   True,  "DuckDuckGo (needs proxy)"),
    ("x",           "https://api.twitter.com/2/openapi.json",    True,  "X / Twitter API (needs proxy)"),
    ("google_html", "https://www.google.com/",                   True,  "Google HTML (needs proxy)"),
    ("baidu",       "https://www.baidu.com/",                    False, "Baidu (direct)"),
    ("douyin",      "https://ark.cn-beijing.volces.com/",        False, "Volcengine / Douyin (direct)"),
]

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


async def _probe(
    session_label: str,
    url: str,
    proxy_url: str | None,
    description: str,
) -> None:
    kwargs: dict = {
        "headers": _DEFAULT_HEADERS,
        "timeout": httpx.Timeout(_PROBE_TIMEOUT),
        "follow_redirects": True,
    }
    if proxy_url:
        kwargs["proxy"] = proxy_url

    route = f"via proxy ({proxy_url})" if proxy_url else "direct"
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(**kwargs) as client:
            resp = await client.get(url)
        elapsed = time.monotonic() - t0
        status_ok = resp.status_code < 500
        msg = f"{description}: HTTP {resp.status_code} in {elapsed:.2f}s [{route}]"
        print(f"  {_ok(msg) if status_ok else _warn(msg)}")
    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(f"  {_fail(f'{description}: {type(exc).__name__}: {exc} in {elapsed:.2f}s [{route}]')}")


async def _print_network(s) -> None:  # noqa: ANN001
    _header("2. Network Connectivity")

    tasks = []
    for engine, url, needs_proxy, description in _PROBES:
        proxy_url = s.proxy_url if needs_proxy else None
        tasks.append(_probe(engine, url, proxy_url, description))

    await asyncio.gather(*tasks)


# --- proxy bypass check ---------------------------------------------------

async def _check_proxy_reachable(proxy_url: str) -> None:
    _header("3. Proxy Reachability")
    # Parse host:port from proxy url
    try:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 7897
    except Exception:
        host, port = "127.0.0.1", 7897

    t0 = time.monotonic()
    try:
        _reader, _writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=3.0,
        )
        _writer.close()
        elapsed = time.monotonic() - t0
        print(_ok(f"Proxy {host}:{port} is reachable ({elapsed:.2f}s)"))
    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(_fail(f"Proxy {host}:{port} unreachable: {exc} ({elapsed:.2f}s)"))
        print(_warn("Proxy engines (google, x, duckduckgo, google_html) will fail"))


# --- main -----------------------------------------------------------------

async def _main() -> None:
    s = _print_config()
    await _check_proxy_reachable(s.proxy_url)
    await _print_network(s)
    print()


if __name__ == "__main__":
    asyncio.run(_main())
