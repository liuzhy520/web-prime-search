# Project Instructions

## Purpose

This is a local-network-proxy-based web search tool that routes queries through X (Twitter), Google, Douyin, and Baidu search engines.

## Core Commands

- No build step is currently defined. Check `package.json` for available scripts before running any build or test commands.
- Review markdown and configuration consistency after any workflow changes.
- Prefer updating canonical instructions and templates together.

## Architecture

- `.github/` contains global instructions, scoped instructions, and agent definitions.
- `.copilot/skills/multi-agent-orchestrator/` contains the skill contract and prompt templates.
- `.ai-control/` contains runtime workflow state and durable context memory.
- `docs/` and `README.md` explain the project and workflow to humans.

## Project Context

- **Goal**: Provide a unified web search interface that automatically routes through local network proxy to X, Google, Douyin, and Baidu.
- **Target user**: 龙虾 (Longxia) and similar users who need cross-platform search via local proxy.
- **Key constraint**: All search traffic must route through the configured local network proxy.

## Conventions

- Treat `.ai-control/session.json` as the source of truth.
- Prefer JSON for machine-updated workflow artifacts.
- Keep handoffs human-readable in markdown.
- Keep instructions concise and operational, not aspirational.
