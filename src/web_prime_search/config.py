from __future__ import annotations

import __main__ as runtime_main
import functools
import os
from pathlib import Path
import sys
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables prefixed with WPS_."""

    x_bearer_token: str = ""
    google_cx: str = ""
    douyin_cookie: str = ""
    volcengine_api_key: str = ""
    volcengine_responses_url: str = "https://ark.cn-beijing.volces.com/api/v3/responses"
    volcengine_web_search_model: str = ""
    proxy_url: str = "http://127.0.0.1:7897"
    engine_timeout_seconds: float = 35.0
    douyin_timeout_seconds: float = 60.0
    google_html_persist_profile: bool = True
    google_html_profile_dir: str = ""
    google_html_cookie_file: str = ""
    google_html_stealth: bool = True
    search_priority: List[str] = [
        "google",
        "duckduckgo",
        "douyin",
        "baidu",
        "x",
        "google_html",
    ]
    proxy_engines: List[str] = ["x", "google", "duckduckgo", "google_html"]
    direct_engines: List[str] = ["douyin", "baidu"]

    model_config = {"env_prefix": "WPS_"}

    def timeout_for_engine(self, engine: str) -> float:
        if engine == "douyin":
            return self.douyin_timeout_seconds
        return self.engine_timeout_seconds


def _iter_env_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def _add(p: Path) -> None:
        if p not in seen:
            candidates.append(p)
            seen.add(p)

    def _iter_parents(start: Path) -> tuple[Path, ...]:
        try:
            resolved = start.resolve()
        except OSError:
            return ()
        return (resolved, *resolved.parents)

    for directory in _iter_env_hint_directories():
        _add(directory / ".env")

    # Primary: walk up from cwd
    cwd = Path.cwd().resolve()
    for directory in (cwd, *cwd.parents):
        _add(directory / ".env")

    # Secondary: walk up from the runtime entrypoint path. This keeps OpenClaw
    # and wrapper-script launches working even when cwd changes unexpectedly.
    for root in _iter_runtime_entry_directories():
        for directory in _iter_parents(root):
            _add(directory / ".env")

    # Fallback: walk up from the package source directory (covers editable installs
    # launched from a cwd outside the project tree, e.g. via OpenClaw)
    pkg_dir = Path(__file__).resolve().parent
    for directory in (pkg_dir, *pkg_dir.parents):
        _add(directory / ".env")

    return tuple(candidates)


def _iter_env_hint_directories() -> tuple[Path, ...]:
    directories: list[Path] = []
    seen: set[Path] = set()

    def _add(raw_path: str) -> None:
        if not raw_path.strip():
            return
        candidate = _normalize_runtime_path(raw_path)
        if candidate is None:
            return
        directory = candidate if candidate.is_dir() else candidate.parent
        if directory not in seen:
            directories.append(directory)
            seen.add(directory)

    for env_name in (
        "WPS_ENV_ROOT",
        "OPENCLAW_SKILL_DIR",
        "OPENCLAW_SKILL_ROOT",
    ):
        _add(os.environ.get(env_name, ""))

    return tuple(directories)


def _iter_runtime_entry_directories() -> tuple[Path, ...]:
    directories: list[Path] = []
    seen: set[Path] = set()

    def _add(path: Path | None) -> None:
        if path is None:
            return
        directory = path if path.is_dir() else path.parent
        if directory not in seen:
            directories.append(directory)
            seen.add(directory)

    argv0 = sys.argv[0].strip() if sys.argv else ""
    _add(_normalize_runtime_path(argv0))

    main_file = getattr(runtime_main, "__file__", "")
    if isinstance(main_file, str):
        _add(_normalize_runtime_path(main_file))

    return tuple(directories)


def _normalize_runtime_path(raw_path: str) -> Path | None:
    if not raw_path.strip():
        return None

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    try:
        return candidate.resolve()
    except OSError:
        return None


def _resolve_env_files() -> tuple[str, ...]:
    # Explicit override takes absolute precedence
    explicit = os.environ.get("WPS_ENV_FILE", "").strip()
    if explicit:
        return (explicit,)

    for env_file in _iter_env_candidates():
        if env_file.is_file():
            return (str(env_file),)
    return ()


def _build_env_file_signature(
    env_files: tuple[str, ...],
) -> tuple[tuple[str, int, int], ...]:
    signature: list[tuple[str, int, int]] = []
    for env_file in env_files:
        stat = Path(env_file).stat()
        signature.append((env_file, stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


def _build_environment_signature() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (key, value)
            for key, value in os.environ.items()
            if key.startswith("WPS_")
        )
    )


@functools.lru_cache(maxsize=8)
def _load_settings(
    env_files: tuple[str, ...],
    env_file_signature: tuple[tuple[str, int, int], ...],
    environment_signature: tuple[tuple[str, str], ...],
) -> Settings:
    del env_file_signature
    del environment_signature
    if env_files:
        return Settings(_env_file=env_files, _env_file_encoding="utf-8")
    return Settings()


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    env_files = _resolve_env_files()
    return _load_settings(
        env_files,
        _build_env_file_signature(env_files),
        _build_environment_signature(),
    )


def _clear_settings_cache() -> None:
    _load_settings.cache_clear()


get_settings.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
