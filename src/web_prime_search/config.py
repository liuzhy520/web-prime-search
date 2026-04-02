from __future__ import annotations

import functools
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables prefixed with WPS_."""

    x_bearer_token: str = ""
    google_api_key: str = ""
    google_cx: str = ""
    douyin_cookie: str = ""
    proxy_url: str = "http://127.0.0.1:7897"
    search_priority: List[str] = ["x", "google", "douyin", "baidu"]
    proxy_engines: List[str] = ["x", "google"]
    direct_engines: List[str] = ["douyin", "baidu"]

    model_config = {"env_prefix": "WPS_"}


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
