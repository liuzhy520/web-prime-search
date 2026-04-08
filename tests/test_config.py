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