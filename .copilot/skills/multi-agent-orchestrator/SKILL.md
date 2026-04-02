---
name: multi-agent-orchestrator
description: "Orchestrates Planner, Executor, and Tester subagents for parallel software delivery with context-aware persisted state under .ai-control/. Use when the user asks for multi-agent collaboration, parallel development, isolated executors, iterative bug fixing, or orchestrator-driven workflows."
---

# Multi-Agent Orchestrator Skill

## Quick Start

1. Read `.ai-control/session.json` if it exists.
2. If resuming, also read `.ai-control/context/compacted.md` and `.ai-control/CLAUDE.md`.
3. Collect git context into `.ai-control/context/git-snapshot.md`.
4. Choose `simple`, `standard`, or `complex` mode based on task count and coupling.
5. Dispatch Planner, Executor, and Tester subagents using prompts that include injected workflow context.
6. Persist all workflow state changes under `.ai-control/`.
7. Compact older context into `.ai-control/context/compacted.md` when the conversation grows long.

## Role Contracts

| Role | Agent Name | Responsibility | May Write `.ai-control/`? | May Write Business Code? |
|------|-----------|---------------|--------------------------|-------------------------|
| Orchestrator | `Orchestrator` | Understand request, maintain state, allocate tasks, dispatch subagents, replan after bugs | Yes | No (unless workflow-control) |
| Planner | `Planner` | Produce planning artifacts: task breakdown, dependencies, acceptance criteria | No | No |
| Executor | `Executor` | Implement exactly one task in one branch/worktree, verify, commit, push | No | Yes (scoped to allowed paths) |
| Tester | `Tester` | Test a target branch/commit, report evidence, draft bug cards | No | No |

## Subagent Dispatch

Use `runSubagent` with the agent names above:

```
runSubagent(agentName="Planner", prompt="<planner instructions>")
runSubagent(agentName="Executor", prompt="<executor instructions>")
runSubagent(agentName="Tester", prompt="<tester instructions>")
```

See [prompts.md](prompts.md) for ready-to-use prompt templates for each role.

## Canonical State Files

All workflow state lives under `.ai-control/`:

| File | Purpose |
|------|---------|
| `session.json` | Machine-readable source of truth + context store |
| `CLAUDE.md` | Project-level instructions |
| `CLAUDE.local.md` | Local-only instructions |
| `context/compacted.md` | Compact summary of earlier conversation |
| `context/git-snapshot.md` | Current git status and diff summary |
| `context/discoveries.md` | Cached exploration findings |
| `tasks/*.json` | Individual task cards |
| `bugs/*.json` | Individual bug cards |
| `handoffs/*.md` | Executor implementation handoffs |

Templates are minimized. The primary schema lives in these instructions and in the JSON task/bug shapes.

## Session Schema

```json
{
	"run_id": "run-001",
	"goal": "<user request>",
	"phase": "planning|executing|testing|complete",
	"context": {
		"compaction_count": 0,
		"preserved_message_count": 4,
		"key_files": [],
		"pending_work": [],
		"tools_used": [],
		"decisions_made": [],
		"current_work_summary": ""
	},
	"tasks": [],
	"bugs": []
}
```

## Context Injection Template

Every subagent prompt must start with:

```text
## Workflow Context (auto-injected)
- Run: <run_id> | Phase: <phase> | Tasks: <total> total, <done> done, <in_progress> in-progress
- Goal: <goal summary>
- Key decisions: <comma-separated decisions>
- Git state: <branch and file summary>
- Compacted summary: <truncated compacted context>
```

Keep the injected context under 2000 characters.

## Workflow Modes

| Mode | Task Count | Behavior |
|------|-----------|----------|
| `simple` | 1-2 | Inline tasks in `session.json`, skip Planner |
| `standard` | 3-5 | Planner + separate JSON task cards |
| `complex` | 6+ | Planner + contract tasks + dependency graph |

## Operating Rules

1. **Only the Orchestrator** may write under `.ai-control/`.
2. Executors and Testers return structured output; they do not persist workflow state directly.
3. Prefer **contract-first tasks** when multiple executor tasks share interfaces or schema.
4. After any executor reports a successful push, mark the task `ready_for_test` and dispatch the Tester.
5. If the Tester reports a failure, create a bug card and reassign through the Orchestrator.
6. Keep task IDs, branch names, and verification commands **aligned across all files**.
7. Do not treat chat history as authoritative if `session.json` or `context/compacted.md` is newer.
8. Compact stale context after roughly 8 conversation turns, preserving the most recent 4 messages/actions.

## Main Agent Loop

1. **Read** session state, compacted context, and project instructions.
2. **Collect** git context.
3. **Decide** workflow mode and whether planning is needed.
4. **Create or refresh** JSON task cards before dispatching executors.
5. **Dispatch** only tasks whose dependencies are satisfied, with injected workflow context.
6. **Persist** all state transitions and merge executor context updates.
7. **Compact** older context when needed.
8. **Repeat** until all tasks are `done` or the user intervenes.

## Prompt Templates

Use the templates in [prompts.md](prompts.md):

- Orchestrator prompt — main agent loop and state management
- Planner prompt — task decomposition and planning
- Executor prompt — scoped implementation with handoff
- Tester prompt — verification and evidence collection
- Bug re-assignment prompt — triage and reassignment
- Optional PUA injection block — pressure-driven behavior modifiers
