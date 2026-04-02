# .ai-control — Workflow State Directory

This directory holds the canonical workflow state for multi-agent orchestrated delivery. Managed exclusively by the Orchestrator agent.

## Structure
- session.json: machine-readable source of truth
- CLAUDE.md: project-level instructions
- context/: compacted memory, git snapshot, discoveries
- tasks/: JSON task cards
- bugs/: JSON bug cards
- handoffs/: executor handoff records
- templates/: workflow schema templates

See CLAUDE.md for project-specific conventions.