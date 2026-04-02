---
description: "Multi-agent orchestration protocol for Copilot Chat. Enables Orchestrator, Planner, Executor, Tester agent modes, context persistence, and skill dispatch. Use when you want parallel, isolated, or resumable workflows."
---

# Copilot Multi-Agent Orchestration Protocol

This workspace uses a four-role agent system for collaborative, context-aware software delivery. See `.github/agents/` for agent definitions and `.copilot/skills/multi-agent-orchestrator/` for workflow skills.

- Only the Orchestrator agent may write to `.ai-control/`.
- Planner, Executor, and Tester have strict role boundaries.
- All workflow state is persisted under `.ai-control/`.
- See `.ai-control/README.md` and `.ai-control/CLAUDE.md` for project-level instructions and workflow state.

Agent modes available in Copilot Chat:
- @Orchestrator
- @Planner
- @Executor
- @Tester
