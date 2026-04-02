---
applyTo: ".ai-control/tasks/**"
---

# Task Isolation

These rules apply when working with task cards and executor assignments.

## Executor Constraints

- Executors may only modify files listed in the assigned task card under `allowed_paths`.
- Read only the paths listed in `allowed_paths` plus any `shared_contracts` explicitly referenced by the task card.
- Do not inspect or modify sibling task cards unless the task card lists them in `depends_on`.
- If a task requires changes outside the allowed paths, stop and report `blocked` to the orchestrator.
- If multiple tasks need the same interface or schema, create or wait for a dedicated contract task before implementation.
- Do not widen scope because a nearby improvement seems convenient; return the risk or follow-up to the orchestrator.

## Task Card Requirements

Every task card must be JSON and define:

- `id` — unique task identifier (e.g. `TASK-001`)
- `title` — short description of the deliverable
- `status` — `todo | in_progress | ready_for_test | done | blocked | failed`
- `owner` — assigned executor agent
- `branch` — dedicated git branch for this task
- `worktree` — dedicated git worktree path
- `allowed_paths` — exhaustive list of paths the executor may modify
- `forbidden_paths` — optional explicit exclusions
- `shared_contracts` — shared schema/API/interface files that may be read
- `depends_on` — prerequisite task IDs
- `acceptance` — acceptance criteria as an array of strings
- `verification` — commands to run before claiming completion

## Cross-Task Contracts

- When multiple tasks share an interface, schema, or API surface, the orchestrator must create a contract task first.
- Contract tasks define the shared artifact and are marked as dependencies for all consuming tasks.
- Executors must not modify contract artifacts unless their task card explicitly allows it.
