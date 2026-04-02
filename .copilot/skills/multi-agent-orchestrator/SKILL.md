---
name: multi-agent-orchestrator
description: "Orchestrates Planner, Executor, and Tester subagents for parallel software delivery with context-aware persisted state under .ai-control/. Use when the user asks for multi-agent collaboration, parallel development, isolated executors, iterative bug fixing, or orchestrator-driven workflows."
---

# Multi-Agent Orchestrator Skill

This skill enables the full multi-agent workflow for Copilot Chat in this workspace. See `.github/agents/` for agent definitions and `.ai-control/README.md` for workflow state rules.

- Orchestrator: manages state, dispatches subagents, persists results
- Planner: task breakdown, dependencies, acceptance criteria
- Executor: implements one task, scoped to allowed paths
- Tester: verifies, reports, drafts bug cards

All workflow state is persisted under `.ai-control/`. See `prompts.md` for ready-to-use subagent prompt templates.