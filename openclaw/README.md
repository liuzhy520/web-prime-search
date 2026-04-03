# OpenClaw Local Skill

This directory packages `web-prime-search` as a local MCP skill for OpenClaw.

## What OpenClaw Should Launch

OpenClaw should start the MCP server from the repository root with:

```bash
python -m web_prime_search serve
```

The process must run with its working directory set to the repository root so the application can auto-load `.env` or `.env.example`.

## Fast Path

1. Create a virtual environment in this repository.
2. Install the package and runtime dependencies.
3. Install the Playwright browser runtime.
4. Copy `.env.example` to `.env` and fill the required values.
5. Run `python -m web_prime_search openclaw-config` and paste the JSON into OpenClaw's local MCP skill config.

## Required Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m playwright install chromium
cp .env.example .env
python -m web_prime_search openclaw-config
```

## Required Environment Variables

- `WPS_GOOGLE_CX` for the Google CSE engine.
- `WPS_VOLCENGINE_API_KEY` and `WPS_VOLCENGINE_WEB_SEARCH_MODEL` for the `douyin` engine.

## Recommended Environment Variables

- `WPS_PROXY_URL` if OpenClaw should route Google, X, and DuckDuckGo through a local proxy.
- `WPS_ENGINE_TIMEOUT_SECONDS` to bound slow engines.

## Files

- `web-prime-search.mcp.json.example`: static example config with placeholder paths.

If your OpenClaw build expects an additional manifest schema beyond a local MCP server definition, keep using the same command, args, and cwd values shown here and adapt only the outer wrapper.