# .ai-control — Workflow State Directory

This directory holds the canonical workflow state for multi-agent orchestrated delivery. It is managed exclusively by the **Orchestrator** agent.

## Directory Structure

```
.ai-control/
├── README.md                  ← this file
├── session.json               ← machine-readable source of truth + context store
├── CLAUDE.md                  ← project-level instructions
├── CLAUDE.local.md            ← local-only instructions (optional, untracked)
├── context/
│   ├── compacted.md           ← compacted conversation summary
│   ├── git-snapshot.md        ← latest git status + diff summary
│   └── discoveries.md         ← cached repository discoveries
├── tasks/                     ← JSON task cards
├── bugs/                      ← JSON bug cards
├── handoffs/                  ← executor handoff records
└── templates/                 ← minimal checked-in schemas/templates
    ├── session.json
    ├── TASK-template.json
    ├── BUG-template.json
    └── HANDOFF-template.md
```

## Rules

1. **Only the Orchestrator** may create or modify files in this directory.
2. Subagents return structured output. The Orchestrator persists it.
3. `session.json` is the machine-readable source of truth.
4. `context/compacted.md` is the canonical long-session memory artifact.
5. Chat history is **not** authoritative when `.ai-control/` has newer state.

## Usage

### Starting a New Workflow

1. Create `session.json` from `templates/session.json`.
2. Create `CLAUDE.md` with project commands, architecture, and conventions.
3. Create `context/` if it does not exist.
4. For standard or complex workflows, create `tasks/TASK-NNN.json` files from `templates/TASK-template.json`.

### During Execution

- Refresh `context/git-snapshot.md` before dispatching subagents.
- Update `session.json` after every task, bug, or compaction event.
- Persist executor handoffs to `handoffs/HANDOFF-NNN.md`.
- Persist bugs to `bugs/BUG-NNN.json`.
- Compact older conversation state into `context/compacted.md` when the session grows long.
