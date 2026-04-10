---
name: web-prime-search
description: "OpenClaw web search skill for Google, DuckDuckGo, Douyin, Baidu, X, and Google HTML via MCP. Use when the agent needs web search, multi-engine search, or an OpenClaw search tool without system-level packaging."
metadata:
  openclaw:
    emoji: "🔎"
    requires:
      anyBins:
        - python3
        - python
    install:
      - name: prepare-repo-venv
        command: python3 -m venv .venv && .venv/bin/pip install -e .
        description: Create a repo-local virtualenv and install the package in editable mode when dependencies are not present yet.
---

# Web Prime Search

This OpenClaw skill runs the repository-local `web-prime-search` application without installing it into the system Python.

## Runtime Contract

- Start the MCP server with `python3 launch.py serve` from this skill directory.
- `launch.py` always prefers the repository-local `.venv` interpreter when it exists.
- `launch.py` sets `WPS_ENV_ROOT` to the repository root and `OPENCLAW_SKILL_DIR` / `OPENCLAW_SKILL_ROOT` to this skill directory before starting the app.
- `launch.py` also prepends the repository `src/` directory to `PYTHONPATH`, so OpenClaw can run the current source tree directly.
- The registered MCP tool name is `web_search`.

## Configuration

- Keep runtime configuration in the repository root `.env` file.
- Copy `.env.template` to `.env` and fill in real values before starting the skill.
- `google` requires `WPS_GOOGLE_CX` only. Do not ask for a Google API key.
- `douyin` requires `WPS_VOLCENGINE_API_KEY` and `WPS_VOLCENGINE_WEB_SEARCH_MODEL`.
- Other settings, including proxy and timeouts, continue to come from the same `.env` file.

## Recommended Startup

Run from the skill directory:

```bash
python3 launch.py serve
```

Optional one-shot CLI usage from the same directory:

```bash
python3 launch.py search --query "今天有什么热点新闻？" --engines duckduckgo --max-results 5
```

## Notes For Agents

- Prefer this skill-local launcher over system-level `pip install` or wheel packaging.
- If the repository `.venv` does not exist yet, create it inside the repository and install dependencies there.
- Do not rename the MCP tool to `web_prime_search`; the tool name is `web_search`.
