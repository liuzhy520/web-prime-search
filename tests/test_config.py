from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from web_prime_search.config import get_settings


def test_get_settings_reads_dotenv_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "WPS_VOLCENGINE_API_KEY=dotenv-key\n"
        "WPS_VOLCENGINE_WEB_SEARCH_MODEL=dotenv-model\n",
        encoding="utf-8",
    )

    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.volcengine_api_key == "dotenv-key"
    assert settings.volcengine_web_search_model == "dotenv-model"


def test_get_settings_ignores_dotenv_example(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import web_prime_search.config as config_module

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.example").write_text(
        "WPS_VOLCENGINE_API_KEY=example-key\n",
        encoding="utf-8",
    )

    # Also anchor __file__ inside tmp_path so the fallback pkg-dir walk
    # doesn't escape to the real project root and load the real .env.
    fake_pkg = tmp_path / "fake_pkg"
    fake_pkg.mkdir()
    with patch.object(config_module, "__file__", str(fake_pkg / "config.py")):
        get_settings.cache_clear()
        try:
            settings = get_settings()
        finally:
            get_settings.cache_clear()

    assert settings.volcengine_api_key == ""


def test_get_settings_reads_parent_dotenv_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    nested_dir = tmp_path / "src" / "nested"
    nested_dir.mkdir(parents=True)
    (tmp_path / ".env").write_text(
        "WPS_GOOGLE_CX=parent-cx\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(nested_dir)

    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.google_cx == "parent-cx"


def test_get_settings_reloads_after_dotenv_change(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("WPS_GOOGLE_CX=first\n", encoding="utf-8")

    get_settings.cache_clear()
    try:
        first = get_settings().google_cx
        env_file.write_text("WPS_GOOGLE_CX=second\n", encoding="utf-8")
        second = get_settings().google_cx
    finally:
        get_settings.cache_clear()

    assert first == "first"
    assert second == "second"


def test_get_settings_wps_env_file_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """WPS_ENV_FILE takes precedence over any directory-based .env discovery."""
    env_file = tmp_path / "custom.env"
    env_file.write_text("WPS_GOOGLE_CX=override-cx\n", encoding="utf-8")

    monkeypatch.setenv("WPS_ENV_FILE", str(env_file))
    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.google_cx == "override-cx"


def test_get_settings_fallback_to_package_dir_dotenv(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """When cwd has no .env, settings fall back to a .env found relative to the package."""
    import web_prime_search.config as config_module

    # cwd is an isolated dir with no .env (sibling of proj, not an ancestor)
    isolated_cwd = tmp_path / "isolated"
    isolated_cwd.mkdir()
    monkeypatch.chdir(isolated_cwd)

    # Fake project tree: tmp_path/proj/pkg/config.py, with .env at tmp_path/proj/.env
    # This is reachable by walking up from pkg but NOT from isolated_cwd.
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    (proj_dir / ".env").write_text("WPS_GOOGLE_CX=pkg-fallback-cx\n", encoding="utf-8")
    fake_pkg = proj_dir / "pkg"
    fake_pkg.mkdir()

    with patch.object(config_module, "__file__", str(fake_pkg / "config.py")):
        get_settings.cache_clear()
        try:
            settings = get_settings()
        finally:
            get_settings.cache_clear()

    assert settings.google_cx == "pkg-fallback-cx"