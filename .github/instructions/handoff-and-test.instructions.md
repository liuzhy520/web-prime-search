---
applyTo: ".ai-control/handoffs/**"
---

# Handoff and Test Contract

These rules apply when working with executor handoffs and tester reports.

## Executor Handoff Format

Executors must return structured JSON containing:

- `task_id` — the task being handed off
- `status` — `success` | `blocked` | `failed`
- `branch` — the branch containing the implementation
- `commit_sha` — the final commit hash
- `changed_paths` — list of files modified
- `verification` — array of `{ command, exit_code, summary }`
- `open_risks` — any risks or concerns discovered during implementation
- `handoff_summary` — short summary for the orchestrator to persist
- `context_update` — incremental context merge payload with optional:
	- `key_files_added`
	- `decisions_made`
	- `pending_work`
	- `open_risks`

## Tester Report Format

Testers must return structured JSON containing:

- `task_id` — the task being tested
- `tested_branch` — the branch tested
- `tested_commit` — the commit hash tested
- `status` — `passed` | `failed` | `blocked`
- `commands_run` — list of commands executed during testing
- `evidence` — array of `{ command, exit_code, summary }`
- `bugs` — array of bug draft objects if failures were found
- `regression_risks` — any regression risks identified

## Boundary Rules

- Testers must not edit business code.
- Executors and testers must not write files under `.ai-control/`; they return structured output to the orchestrator.
- The orchestrator is responsible for persisting session state, bug cards, handoffs, and context updates.
- A task may be marked complete only after verification evidence is present.
