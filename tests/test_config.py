from __future__ import annotations

from pathlib import Path

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
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.example").write_text(
        "WPS_VOLCENGINE_API_KEY=example-key\n",
        encoding="utf-8",
    )

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