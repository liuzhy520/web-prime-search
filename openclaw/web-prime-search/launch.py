from __future__ import annotations

import os
from pathlib import Path
import sys


def _build_env(repo_root: Path, skill_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("WPS_ENV_ROOT", str(repo_root))
    env.setdefault("OPENCLAW_SKILL_DIR", str(repo_root))
    env.setdefault("OPENCLAW_SKILL_ROOT", str(repo_root))

    src_dir = repo_root / "src"
    existing_pythonpath = env.get("PYTHONPATH", "")
    path_parts = [str(src_dir)]
    if existing_pythonpath:
        path_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(path_parts)
    return env


def _resolve_repo_python(repo_root: Path) -> str:
    candidates = [
        repo_root / ".venv" / "bin" / "python",
        repo_root / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    skill_root = Path(__file__).resolve().parent
    repo_root = skill_root.parents[1]
    python_executable = _resolve_repo_python(repo_root)
    env = _build_env(repo_root, skill_root)

    os.execvpe(
        python_executable,
        [python_executable, "-m", "web_prime_search", *args],
        env,
    )


if __name__ == "__main__":
    main()
