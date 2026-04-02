# Handoff — TASK-000

Return executor handoffs as JSON inside a fenced code block using this shape:

```json
{
	"task_id": "TASK-000",
	"status": "success",
	"branch": "feat/TASK-000-short-name",
	"commit_sha": "abc1234",
	"changed_paths": [
		"path/to/file"
	],
	"verification": [
		{
			"command": "npm test",
			"exit_code": 0,
			"summary": "12 tests passed"
		}
	],
	"open_risks": [
		"Describe any remaining risk"
	],
	"handoff_summary": "Provide a short summary that the orchestrator can persist without rewriting.",
	"context_update": {
		"key_files_added": [
			"path/to/file"
		],
		"decisions_made": [
			"Record important implementation decisions"
		],
		"pending_work": [],
		"open_risks": [
			"Repeat any risk that should enter session context"
		]
	}
}
```
