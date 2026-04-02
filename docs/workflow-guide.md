# Workflow Guide

A detailed walkthrough of the multi-agent orchestration workflow for VS Code GitHub Copilot.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Workflow Phases](#workflow-phases)
  - [Phase 1: Initialization](#phase-1-initialization)
  - [Phase 2: Planning](#phase-2-planning)
  - [Phase 3: Task Creation](#phase-3-task-creation)
  - [Phase 4: Execution](#phase-4-execution)
  - [Phase 5: Testing](#phase-5-testing)
  - [Phase 6: Bug Handling](#phase-6-bug-handling)
  - [Phase 7: Completion](#phase-7-completion)
- [State Management](#state-management)
- [Parallel Execution](#parallel-execution)
- [Contract Tasks](#contract-tasks)
- [Example Walkthrough](#example-walkthrough)

---

## Overview

The multi-agent orchestration system uses four specialized roles to deliver software changes:

```
User Request → Orchestrator → Planner → Task Cards → Executor(s) → Tester(s) → Done
                    ↑                                                    │
                    └──────────── Bug Re-assignment ←────────────────────┘
```

Each role has strict boundaries:
- **Orchestrator**: Manages state, context memory, and dispatch. Only writer of `.ai-control/`.
- **Planner**: Plans tasks. Read-only, no code changes.
- **Executor**: Implements one task. Scoped to allowed paths, one branch per task.
- **Tester**: Tests and reports. Read-only for business code.

The updated workflow also adds a context management layer:

- `session.json` stores workflow state and compacted memory metadata.
- `context/compacted.md` stores summarized earlier conversation history.
- `context/git-snapshot.md` stores the latest git status and diff summary.
- `CLAUDE.md` stores project-level instructions injected into subagent prompts.

## Prerequisites

1. VS Code with GitHub Copilot extension installed.
2. This repository cloned locally.
3. Agent modes visible in Copilot Chat (the `.github/agents/*.agent.md` files define them).

## Workflow Phases

### Phase 1: Initialization

The Orchestrator reads or creates the workflow state.

**If starting fresh:**

1. User opens Copilot Chat, selects **@Orchestrator**.
2. User describes the request (e.g., "Add Baidu search integration to the proxy router").
3. Orchestrator creates:
  - `.ai-control/session.json` — from `templates/session.json`
  - `.ai-control/CLAUDE.md` — project instructions
  - `.ai-control/context/git-snapshot.md` — current git snapshot

4. Orchestrator chooses workflow mode:
  - `simple` for 1-2 obvious tasks
  - `standard` for 3-5 tasks
  - `complex` for 6+ tasks or contract-heavy work

**If resuming:**

1. Orchestrator reads `.ai-control/session.json`.
2. Reads `.ai-control/context/compacted.md` if present.
3. Reads `.ai-control/CLAUDE.md` if present.
4. Refreshes `.ai-control/context/git-snapshot.md`.
5. Determines next action based on persisted state and compacted context.

### Phase 2: Planning

The Orchestrator dispatches the Planner subagent.

```
runSubagent(
  agentName="Planner",
  prompt="<workflow context preamble>\nGoal: <user request>. Read .ai-control/session.json and the repository. Return complexity mode, task breakdown, dependencies, acceptance criteria, and test recommendations."
)
```

The Planner returns:
- Complexity recommendation (`simple | standard | complex`)
- Task breakdown with IDs, titles, allowed paths
- Dependency graph
- Parallelization advice
- Test recommendations
- Risks and blockers

The Orchestrator persists the result into `.ai-control/session.json` and, when needed, `tasks/TASK-NNN.json` files.

### Phase 3: Task Creation

The Orchestrator creates task cards from the Planner's output.

For each task:
1. Copy `.ai-control/templates/TASK-template.json` to `.ai-control/tasks/TASK-NNN.json`.
2. Fill in: `id`, `title`, `owner`, `branch`, `worktree`, `allowed_paths`, `forbidden_paths`, `shared_contracts`, `depends_on`, `acceptance`, `verification`.
3. Update `session.json` with the new task.
4. For simple mode, inline tasks directly in `session.json` and skip separate task files.

### Phase 4: Execution

The Orchestrator dispatches Executor subagents for tasks whose dependencies are satisfied.

```
runSubagent(
  agentName="Executor",
  prompt="<workflow context preamble>\nTask card: .ai-control/tasks/TASK-001.json. Branch: feat/TASK-001-search-router. Worktree: ../wt-TASK-001. Read the task card, implement, verify, commit, push, and return JSON output with context_update."
)
```

**Executor workflow:**
1. Read task card → extract allowed paths, acceptance, verification.
2. Read injected workflow context.
3. Create branch and worktree:
   ```bash
   git worktree add ../wt-TASK-001 -b feat/TASK-001-search-router
   ```
4. Capture git status and diff summary.
5. Implement within allowed paths.
6. Run verification commands.
7. Commit and push.
8. Return structured JSON handoff including `context_update`.

**After executor returns:**
- Orchestrator persists handoff to `.ai-control/handoffs/HANDOFF-TASK-001.md`.
- Updates task status to `ready_for_test` in `session.json`.
- Merges executor `context_update` into `session.json.context`.
- If executor returned `blocked`, investigates and replans.

### Phase 5: Testing

The Orchestrator dispatches the Tester subagent.

```
runSubagent(
  agentName="Tester",
  prompt="<workflow context preamble>\nTask card: .ai-control/tasks/TASK-001.json. Branch: feat/TASK-001-search-router. Commit: abc1234. Run verification and regression tests. Return structured JSON report."
)
```

**Tester workflow:**
1. Check out the target branch/commit.
2. Run verification commands from the task card.
3. Run any additional tests from the test plan.
4. Produce evidence (command output, logs).
5. If failures found, draft bug cards.
6. Return structured test report.

**After tester returns:**
- If `passed` → mark task `done`.
- If `failed` → create JSON bug cards, enter bug handling flow.

### Phase 6: Bug Handling

When a tester reports failures:

1. Orchestrator creates bug cards in `.ai-control/bugs/BUG-NNN.json`.
2. Decides resolution strategy:
   - **Reassign** to original executor with updated criteria.
   - **New task** if the fix requires different scope.
   - **Won't fix** if out of scope.
3. Dispatches the appropriate executor with the bug context.
4. After fix, dispatches tester for retest.

### Phase 7: Completion

When all tasks are `done`:

1. Orchestrator updates `session.json` with `phase: "complete"`.
2. Summarizes the run: tasks completed, bugs fixed, remaining risks.
3. Reports final status to the user.

## State Management

### Source of Truth Hierarchy

1. `.ai-control/session.json` — machine-readable, canonical
2. `.ai-control/context/compacted.md` — canonical compressed long-session memory
3. `.ai-control/tasks/*.json` and `.ai-control/bugs/*.json` — detailed workflow artifacts
4. Chat history — supplementary only, not authoritative

### State Transitions

```
Task:  todo → in_progress → ready_for_test → done
                  │                   │
                  ▼                   ▼
               blocked          failed_test → in_progress (reassigned)

Bug:   open → in_fix → retest → closed
                         │
                         ▼
                      rejected
```

### Keeping State Aligned

The Orchestrator must ensure consistency between:
- `session.json` task entries
- JSON task cards
- Bug cards
- Branch names and worktree paths

## Context Compaction

When the conversation grows long, the Orchestrator compacts earlier turns.

### Trigger

- After roughly 8 turns
- Or when the conversation becomes repetitive or stale

### Compaction Strategy

1. Preserve the most recent 4 messages/actions verbatim.
2. Summarize earlier context into `.ai-control/context/compacted.md` with:
  - scope
  - tools used
  - key files
  - recent user requests
  - pending work
  - current work
  - timeline
3. Increment `context.compaction_count` in `session.json`.

### Session Resumption

On resume, the Orchestrator injects the compacted summary and continues without recapping or asking the user to repeat prior context.

## Parallel Execution

### When to Parallelize

Tasks can run in parallel when:
- They have no dependencies on each other.
- They modify non-overlapping file paths.
- Any shared interfaces are defined in completed contract tasks.

### Parallel Topology Example

```
TASK-001 (proxy router)  ──┐
                            ├──→ TASK-004 (integration tests)
TASK-002 (search adapter) ──┘
                               │
TASK-003 (UI scaffolding)      ▼
         │              TASK-005 (E2E tests)
         └──────────────────────┘
```

- **Parallel group 1**: TASK-001, TASK-002, TASK-003 (independent)
- **Serial after group 1**: TASK-004 (depends on TASK-001, TASK-002)
- **Serial after all**: TASK-005 (depends on TASK-003, TASK-004)

## Contract Tasks

When multiple executor tasks share an interface, schema, or API surface:

1. The Orchestrator creates a **contract task** that defines the shared artifact.
2. The contract task is marked as a dependency for all consuming tasks.
3. The contract executor implements only the shared definition (types, interfaces, schemas).
4. Consumer tasks are dispatched only after the contract task is `done`.

**Example:**

```
TASK-001: Define SearchProvider interface (contract task)
TASK-002: Implement Google search adapter (depends on TASK-001)
TASK-003: Implement Baidu search adapter (depends on TASK-001)
```

## Example Walkthrough

### Scenario: "Add Douyin search support to the proxy router"

**Step 1 — User invokes @Orchestrator:**
> "Add Douyin video search to the proxy router. Results should include video title, author, and URL."

**Step 2 — Orchestrator dispatches Planner:**
- Creates `.ai-control/session.json` with `run_id: "run-001"`.
- Dispatches `runSubagent(agentName="Planner", ...)`.

**Step 3 — Planner returns task breakdown:**
```
TASK-001: Define SearchResult interface (contract)
TASK-002: Implement Douyin search adapter (depends on TASK-001)
TASK-003: Add Douyin route to proxy router (depends on TASK-001)
TASK-004: Integration tests (depends on TASK-002, TASK-003)
```

**Step 4 — Orchestrator creates task cards and dispatches TASK-001:**
- Creates `.ai-control/tasks/TASK-001.json` through `TASK-004.json`.
- Dispatches Executor for TASK-001 (no dependencies).

**Step 5 — TASK-001 executor completes, Orchestrator dispatches TASK-002 and TASK-003 in parallel:**
- TASK-001 marked `done`.
- TASK-002 and TASK-003 dispatched simultaneously.

**Step 6 — Both executors complete, Orchestrator dispatches testers:**
- Tester for TASK-002: runs adapter tests → passes.
- Tester for TASK-003: runs router tests → finds a bug (proxy header missing).

**Step 7 — Orchestrator handles the bug:**
- Creates `BUG-001` (source: TASK-003, severity: medium).
- Reassigns to TASK-003's executor with updated acceptance criteria.
- Executor fixes, pushes. Tester retests → passes.

**Step 8 — TASK-004 dispatched (all dependencies satisfied):**
- Executor runs integration tests, all pass.
- Tester verifies. Orchestrator marks all tasks `done`.

**Step 9 — Orchestrator reports completion:**
> "Run run-001 complete. 4 tasks delivered, 1 bug found and fixed. Douyin search is live."
