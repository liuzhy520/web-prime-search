# Multi-Agent Base Protocol

This file is the canonical base protocol for orchestrated multi-agent delivery with context-aware memory management. It applies to every Copilot conversation in this workspace.

## Core Rules

- Treat `.ai-control/session.json` as the canonical workflow state and context store.
- Read `.ai-control/session.json` before substantial work if it exists.
- Only the orchestrator agent may create or update files under `.ai-control/`.
- Planner only plans. Tester only tests. Executors only implement assigned tasks.
- Do not rely on chat history as the source of truth when `.ai-control/` has newer state.

## Role Summary

| Role | Responsibility | May Write `.ai-control/`? | May Write Business Code? |
|------|---------------|--------------------------|-------------------------|
| Orchestrator | Understand request, maintain state, manage context, dispatch subagents, replan after bugs | Yes | No (unless workflow-control task) |
| Planner | Produce planning artifacts: task breakdown, dependencies, acceptance criteria | No | No |
| Executor | Implement exactly one task in one branch/worktree, verify, commit, push | No | Yes (scoped to allowed paths) |
| Tester | Test a target branch/commit, report evidence, draft bug cards | No | No |

## Workflow State Files

All workflow state lives under `.ai-control/`:

- `session.json` — machine-readable source of truth (replaces state.json)
- `CLAUDE.md` — project-level instructions (build commands, conventions, architecture)
- `CLAUDE.local.md` — local instructions (not committed)
- `context/compacted.md` — compacted conversation summary
- `context/git-snapshot.md` — latest git state snapshot
- `context/discoveries.md` — cached codebase exploration findings
- `tasks/TASK-NNN.json` — individual task cards (JSON format)
- `bugs/BUG-NNN.json` — individual bug cards (JSON format)
- `handoffs/HANDOFF-NNN.md` — executor implementation handoffs

## Subagent Dispatch

Use `runSubagent` with the following agent names for multi-agent orchestration:

- `Orchestrator` — main agent loop, state management, dispatch
- `Planner` — read-only planning and task decomposition
- `Executor` — scoped implementation of a single task
- `Tester` — read-only testing and evidence collection

## Context Management Protocol

### Session Persistence

`session.json` stores both workflow state AND compressed context:

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

### Context Compaction

When conversations grow long, the Orchestrator must compress earlier context:

1. **Trigger**: After 8+ conversation turns, or when context feels repetitive/stale.
2. **Preserve**: Keep the most recent 4 messages/actions verbatim.
3. **Summarize**: Compress earlier context into a structured summary:
   - Scope: how many messages were compacted
   - Tools mentioned (file paths explored, commands run)
   - Key files referenced in the conversation
   - Recent user requests (last 3)
   - Pending work items
   - Current work in progress
   - Key timeline of decisions and actions
4. **Write**: Save the summary to `.ai-control/context/compacted.md`.
5. **Update**: Increment `context.compaction_count` in `session.json`.

### Session Resumption

When starting a new conversation with an existing `.ai-control/session.json`:

1. Read `session.json` to restore workflow state.
2. Read `context/compacted.md` if it exists to restore conversation context.
3. Read `CLAUDE.md` for project-level instructions.
4. Inject this preamble into your working context:
   ```
   This session continues from a previous conversation.
   [compacted context summary]
   Recent messages are preserved verbatim.
   Continue without recapping or asking about the summary.
   ```
5. Do NOT ask the user to repeat their request — resume from where the last session left off.

### Git Context Collection

At the start of orchestration and before dispatching any subagent:

1. Run `git status --short --branch` to capture current state.
2. Run `git diff --stat` to capture change summary.
3. Write results to `.ai-control/context/git-snapshot.md`.
4. Include a 1-2 line git state summary in every subagent dispatch prompt.

### Instruction File Discovery

Discover project-level instruction files by searching upward from the working directory:

1. Look for: `CLAUDE.md`, `CLAUDE.local.md`, `.claude/CLAUDE.md`, `.claude/instructions.md`
2. Search from the current directory up to the repository root.
3. Deduplicate by content hash.
4. Truncate individual files to 4000 characters.
5. Total injection budget: 12000 characters across all instruction files.
6. Inject discovered instructions into the system context for every subagent.

### Subagent Context Injection

Every subagent dispatch prompt MUST include a context preamble (max 2000 chars):

```
## Workflow Context (auto-injected)
- Run: <run_id> | Phase: <phase> | Tasks: <total> total, <done> done, <in_progress> in-progress
- Goal: <goal summary>
- Key decisions: <comma-separated list from session.json context.decisions_made>
- Git state: <branch, files modified summary>
- Compacted summary: <truncated content from context/compacted.md>
```

## Progressive Complexity

The workflow automatically scales based on task count:

| Mode | Task Count | Behavior |
|------|-----------|----------|
| **Simple** | 1-2 | Tasks inline in session.json. Skip Planner. Orchestrator dispatches directly. |
| **Standard** | 3-5 | Full planning cycle. Separate task JSON files. Standard Executor + Tester flow. |
| **Complex** | 6+ | Full planning + contract tasks + parallel topology + dependency graph. |

The Orchestrator determines the mode after the Planner returns (or immediately for obvious simple tasks).
