from __future__ import annotations

import functools
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables prefixed with WPS_."""

    x_bearer_token: str = ""
    google_api_key: str = ""
    google_cx: str = ""
    douyin_cookie: str = ""
    volcengine_api_key: str = ""
    volcengine_responses_url: str = "https://ark.cn-beijing.volces.com/api/v3/responses"
    volcengine_web_search_model: str = ""
    proxy_url: str = "http://127.0.0.1:7897"
    engine_timeout_seconds: float = 35.0
    search_priority: List[str] = ["google", "douyin", "duckduckgo", "baidu", "x"]
    proxy_engines: List[str] = ["x", "google", "duckduckgo"]
    direct_engines: List[str] = ["douyin", "baidu"]

    model_config = {"env_prefix": "WPS_"}


def _resolve_env_files() -> tuple[str, ...]:
    env_files: list[str] = []
    for candidate in (".env.example", ".env"):
        if Path(candidate).is_file():
            env_files.append(candidate)
    return tuple(env_files)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    env_files = _resolve_env_files()
    if env_files:
        return Settings(_env_file=env_files, _env_file_encoding="utf-8")
    return Settings()
