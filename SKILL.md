---
name: web-prime-search
version: v0.3.6
date: 2026-04-10
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

- Start the MCP server from the repository root with `python3 openclaw/web-prime-search/launch.py serve`.
- `launch.py` always prefers the repository-local `.venv` interpreter when it exists.
- `launch.py` sets `WPS_ENV_ROOT`, `OPENCLAW_SKILL_DIR`, and `OPENCLAW_SKILL_ROOT` to the repository root before starting the app.
- `launch.py` also prepends the repository `src/` directory to `PYTHONPATH`, so OpenClaw can run the current source tree directly.
- The registered MCP tool name is `web_search`.

## Configuration

- Keep runtime configuration in the repository root `.env` file.
- Copy `.env.template` to `.env` and fill in real values before starting the skill.
- `google` requires `WPS_GOOGLE_CX` only. Do not ask for a Google API key.
- `douyin` requires `WPS_VOLCENGINE_API_KEY` and `WPS_VOLCENGINE_WEB_SEARCH_MODEL`.
- Other settings, including proxy and timeouts, continue to come from the same `.env` file.

## Recommended Startup

Run from the repository root:

```bash
python3 openclaw/web-prime-search/launch.py serve
```

Optional one-shot CLI usage from the repository root:

```bash
python3 openclaw/web-prime-search/launch.py search --query "今天有什么热点新闻？" --engines duckduckgo --max-results 5
```

## Notes For Agents

- Prefer the launcher at `openclaw/web-prime-search/launch.py` over system-level `pip install` or wheel packaging.
- If the repository `.venv` does not exist yet, create it inside the repository and install dependencies there.
- Do not rename the MCP tool to `web_prime_search`; the tool name is `web_search`.