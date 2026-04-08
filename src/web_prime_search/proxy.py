from __future__ import annotations

from typing import Optional

import httpx

from web_prime_search.config import Settings, get_settings

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def get_http_client(
    engine: str,
    settings: Optional[Settings] = None,
) -> httpx.AsyncClient:
    """Return an ``httpx.AsyncClient`` with per-engine proxy routing.

    Engines listed in ``settings.proxy_engines`` get a client configured to
    route traffic through ``settings.proxy_url``.  All other engines receive a
    direct (no-proxy) client.

    The caller is responsible for closing the returned client.
    """
    if settings is None:
        settings = get_settings()

    kwargs: dict = {
        "headers": _DEFAULT_HEADERS,
        "timeout": httpx.Timeout(settings.timeout_for_engine(engine)),
    }

    if engine in settings.proxy_engines:
        kwargs["proxy"] = settings.proxy_url

    return httpx.AsyncClient(**kwargs)
