from __future__ import annotations

import httpx
import pytest

from web_prime_search.config import Settings
from web_prime_search.proxy import get_http_client


@pytest.fixture()
def settings() -> Settings:
    return Settings()


def _has_proxy_mount(client: httpx.AsyncClient) -> bool:
    """Return True if the client has an ``all://`` proxy mount pattern."""
    return any(k.pattern == "all://" for k in client._mounts)


class TestGetHttpClient:
    """Tests for get_http_client proxy/direct routing."""

    def test_proxy_engine_x(self, settings: Settings) -> None:
        client = get_http_client("x", settings=settings)
        assert isinstance(client, httpx.AsyncClient)
        assert _has_proxy_mount(client), "Expected proxy transport for engine 'x'"

    def test_proxy_engine_google(self, settings: Settings) -> None:
        client = get_http_client("google", settings=settings)
        assert _has_proxy_mount(client), "Expected proxy transport for engine 'google'"

    def test_direct_engine_baidu(self, settings: Settings) -> None:
        client = get_http_client("baidu", settings=settings)
        assert isinstance(client, httpx.AsyncClient)
        assert not _has_proxy_mount(client), "Expected no proxy for engine 'baidu'"

    def test_direct_engine_douyin(self, settings: Settings) -> None:
        client = get_http_client("douyin", settings=settings)
        assert not _has_proxy_mount(client), "Expected no proxy for engine 'douyin'"

    def test_unknown_engine_is_direct(self, settings: Settings) -> None:
        client = get_http_client("unknown", settings=settings)
        assert not _has_proxy_mount(client), "Unknown engine should get direct client"

    def test_custom_settings_proxy_engines(self) -> None:
        custom = Settings(proxy_engines=["baidu"], direct_engines=["x", "google", "douyin"])
        client = get_http_client("baidu", settings=custom)
        assert _has_proxy_mount(client), "baidu should use proxy with custom settings"

        client_x = get_http_client("x", settings=custom)
        assert not _has_proxy_mount(client_x), "x should be direct with custom settings"

    def test_default_timeout(self, settings: Settings) -> None:
        client = get_http_client("x", settings=settings)
        assert client.timeout.connect == 30.0
        assert client.timeout.read == 30.0

    def test_default_user_agent(self, settings: Settings) -> None:
        client = get_http_client("x", settings=settings)
        assert "Mozilla" in client.headers.get("user-agent", "")
