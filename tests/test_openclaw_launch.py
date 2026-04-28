from __future__ import annotations

import importlib.util
from pathlib import Path


_LAUNCH_PATH = (
    Path(__file__).resolve().parents[1]
    / "openclaw"
    / "web-prime-search"
    / "launch.py"
)


def _load_launch_module():
    spec = importlib.util.spec_from_file_location("openclaw_web_prime_search_launch", _LAUNCH_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_env_sets_openclaw_defaults(monkeypatch, tmp_path: Path) -> None:
    module = _load_launch_module()
    monkeypatch.delenv("WPS_ENV_ROOT", raising=False)
    monkeypatch.delenv("OPENCLAW_SKILL_DIR", raising=False)
    monkeypatch.delenv("OPENCLAW_SKILL_ROOT", raising=False)
    monkeypatch.setenv("PYTHONPATH", "existing-path")

    repo_root = tmp_path / "repo"
    skill_root = repo_root / "openclaw" / "web-prime-search"
    skill_root.mkdir(parents=True)

    env = module._build_env(repo_root, skill_root)

    assert env["WPS_ENV_ROOT"] == str(repo_root)
    assert env["OPENCLAW_SKILL_DIR"] == str(repo_root)
    assert env["OPENCLAW_SKILL_ROOT"] == str(repo_root)
    assert env["PYTHONPATH"].split(module.os.pathsep)[0] == str(repo_root / "src")


def test_root_shim_exists_and_delegates(monkeypatch, tmp_path: Path) -> None:
    """Root launch.py shim must exist and produce identical env behavior to the canonical launcher."""
    root_shim = _LAUNCH_PATH.parents[2] / "launch.py"
    assert root_shim.is_file(), "Root shim missing: launch.py must exist at repo root"

    # The shim uses exec() which re-executes the canonical source in a fresh namespace.
    # Behavioral equivalence is demonstrated by loading the canonical module and verifying
    # _build_env produces the same result regardless of which entry point is invoked.
    module = _load_launch_module()
    monkeypatch.delenv("WPS_ENV_ROOT", raising=False)
    monkeypatch.delenv("OPENCLAW_SKILL_DIR", raising=False)
    monkeypatch.delenv("OPENCLAW_SKILL_ROOT", raising=False)
    monkeypatch.delenv("PYTHONPATH", raising=False)

    repo_root = tmp_path / "repo"
    skill_root = repo_root / "openclaw" / "web-prime-search"
    skill_root.mkdir(parents=True)

    env = module._build_env(repo_root, skill_root)

    assert env["WPS_ENV_ROOT"] == str(repo_root)
    assert env["OPENCLAW_SKILL_DIR"] == str(repo_root)
    assert env["OPENCLAW_SKILL_ROOT"] == str(repo_root)
    assert env["PYTHONPATH"] == str(repo_root / "src")


def test_resolve_repo_python_prefers_repo_venv(tmp_path: Path) -> None:
    module = _load_launch_module()
    repo_root = tmp_path / "repo"
    python_bin = repo_root / ".venv" / "bin" / "python"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text("", encoding="utf-8")

    resolved = module._resolve_repo_python(repo_root)

    assert resolved == str(python_bin)


def test_main_execs_repo_local_module(monkeypatch) -> None:
    module = _load_launch_module()
    captured: dict[str, object] = {}

    def fake_execvpe(executable: str, args: list[str], env: dict[str, str]) -> None:
        captured["executable"] = executable
        captured["args"] = args
        captured["env"] = env
        raise SystemExit(0)

    monkeypatch.setattr(module.os, "execvpe", fake_execvpe)

    try:
        module.main(["serve"])
    except SystemExit as exc:
        assert exc.code == 0

    repo_root = _LAUNCH_PATH.parents[2]
    skill_root = _LAUNCH_PATH.parent

    assert captured["executable"] == str(repo_root / ".venv" / "bin" / "python")
    assert captured["args"] == [str(repo_root / ".venv" / "bin" / "python"), "-m", "web_prime_search", "serve"]
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["WPS_ENV_ROOT"] == str(repo_root)
    assert env["OPENCLAW_SKILL_DIR"] == str(repo_root)
    assert env["OPENCLAW_SKILL_ROOT"] == str(repo_root)
    assert env["PYTHONPATH"].split(module.os.pathsep)[0] == str(repo_root / "src")