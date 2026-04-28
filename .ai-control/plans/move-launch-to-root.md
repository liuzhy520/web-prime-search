# Plan: Move `launch.py` to Project Root with Backward-Compatible Shim

## Problem

Hermes agent searches relative to the project's default working directory (the repo root).  
`launch.py` is currently buried at `openclaw/web-prime-search/launch.py` — two levels deep.  
This causes Hermes to fail to locate the launcher unless it explicitly knows the nested path.

---

## Goal

Promote `launch.py` to the repo root so any agent or user running from the default working directory can invoke it directly:

```bash
python3 launch.py serve
```

Preserve the old path as a backward-compatible shim so existing configs using `openclaw/web-prime-search/launch.py` continue to work without changes.

---

## Steps

### Step 1 — Create root-level `launch.py`

Create `launch.py` at the repo root (`/launch.py`).

Logic is the same as the current file except the `repo_root` derivation in `main()` changes:

| Location | `repo_root` derivation |
|---|---|
| `openclaw/web-prime-search/launch.py` (old) | `Path(__file__).resolve().parents[1]` |
| `launch.py` (new root) | `Path(__file__).resolve().parent` |

All other functions (`_build_env`, `_resolve_repo_python`) remain identical.

```python
# launch.py (repo root)
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
    repo_root = Path(__file__).resolve().parent   # <-- changed from .parents[1]
    skill_root = repo_root                        # skill_root == repo_root when at root
    python_executable = _resolve_repo_python(repo_root)
    env = _build_env(repo_root, skill_root)

    os.execvpe(
        python_executable,
        [python_executable, "-m", "web_prime_search", *args],
        env,
    )


if __name__ == "__main__":
    main()
```

---

### Step 2 — Replace old file with a backward-compatible shim

Replace `openclaw/web-prime-search/launch.py` with a minimal shim that delegates to the root launcher via `runpy.run_path`. Single source of truth — no duplicated logic.

```python
# openclaw/web-prime-search/launch.py  (shim — backward compat only)
"""Backward-compatible shim. Delegates to the canonical launcher at the repo root."""
from __future__ import annotations

import runpy
from pathlib import Path

_ROOT_LAUNCHER = Path(__file__).resolve().parents[2] / "launch.py"

runpy.run_path(str(_ROOT_LAUNCHER), run_name="__main__")
```

---

### Step 3 — Update tests

File: `tests/test_openclaw_launch.py`

**3a.** Change `_LAUNCH_PATH` to point to the root launcher:

```python
# before
_LAUNCH_PATH = (
    Path(__file__).resolve().parents[1]
    / "openclaw"
    / "web-prime-search"
    / "launch.py"
)

# after
_LAUNCH_PATH = Path(__file__).resolve().parents[1] / "launch.py"
```

**3b.** Fix `test_main_execs_repo_local_module` — `repo_root` is now `_LAUNCH_PATH.parent` (not `.parents[2]`):

```python
# before
repo_root = _LAUNCH_PATH.parents[2]
skill_root = _LAUNCH_PATH.parent

# after
repo_root = _LAUNCH_PATH.parent
skill_root = _LAUNCH_PATH.parent
```

**3c.** Add a shim smoke test to confirm backward compatibility:

```python
def test_shim_delegates_to_root_launcher(monkeypatch, tmp_path: Path) -> None:
    """The shim at openclaw/web-prime-search/launch.py must resolve to the root launcher path."""
    shim_path = (
        Path(__file__).resolve().parents[1]
        / "openclaw"
        / "web-prime-search"
        / "launch.py"
    )
    assert shim_path.is_file(), "Shim file missing"
    source = shim_path.read_text(encoding="utf-8")
    # The shim must reference the root launch.py two levels up
    assert "parents[2]" in source, "Shim must navigate to repo root via parents[2]"
    assert "launch.py" in source, "Shim must reference root launch.py"
```

---

### Step 4 — Update `SKILL.md`

File: `SKILL.md`

| Field | Before | After |
|---|---|---|
| `metadata.openclaw.run.command` | `python3 openclaw/web-prime-search/launch.py serve` | `python3 launch.py serve` |
| Prose (Runtime Contract) | `python3 openclaw/web-prime-search/launch.py serve` | `python3 launch.py serve` |
| Recommended Startup code block | `python3 openclaw/web-prime-search/launch.py serve` | `python3 launch.py serve` |
| One-shot CLI code block | `python3 openclaw/web-prime-search/launch.py search …` | `python3 launch.py search …` |
| Notes For Agents | `openclaw/web-prime-search/launch.py` | `launch.py` |

Also add a note in **Notes For Agents** that `openclaw/web-prime-search/launch.py` still works as a backward-compatible shim.

---

### Step 5 — Update `README.md`

File: `README.md`

Update the launcher path reference:

```
# before
- 仓库内 launcher 位于 [openclaw/web-prime-search/launch.py](openclaw/web-prime-search/launch.py)，启动时使用：`python3 openclaw/web-prime-search/launch.py serve`。

# after
- 仓库内 launcher 位于 [launch.py](launch.py)，启动时使用：`python3 launch.py serve`。`openclaw/web-prime-search/launch.py` 保留为向后兼容的 shim。
```

---

## Files Changed

| File | Change |
|---|---|
| `launch.py` *(new)* | Canonical root launcher; `repo_root = Path(__file__).resolve().parent` |
| `openclaw/web-prime-search/launch.py` | Replaced with `runpy.run_path` shim delegating to root |
| `tests/test_openclaw_launch.py` | `_LAUNCH_PATH` updated; `repo_root` assertion fixed; shim smoke test added |
| `SKILL.md` | All `openclaw/web-prime-search/launch.py` references → `launch.py` |
| `README.md` | Launcher path reference updated |

---

## Verification

```bash
# 1. New canonical path works from repo root
python3 launch.py serve

# 2. Old path still works via shim
python3 openclaw/web-prime-search/launch.py serve

# 3. Tests pass
pytest tests/test_openclaw_launch.py -v
```

All three must succeed with no errors.

---

## Constraints

- No logic is duplicated between root `launch.py` and the shim — the shim is a pure delegate.
- `skill_root` parameter in `_build_env` is retained as-is (still passed from `main()`).
- No new markdown documentation files are created beyond this plan (per project conventions).
