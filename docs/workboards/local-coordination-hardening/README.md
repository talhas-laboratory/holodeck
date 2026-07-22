# Local Coordination Hardening

Purpose: coordinate multi-agent work with sparse, reliable task state, decision history, and mandatory completion gates.

Board id: `local-coordination-hardening`
Owner: `talha`
Created: `2026-07-22T17:59:34.720965+00:00`

## Agent Start Protocol

1. Read `README.md`, `TASKS.md`, `GATES.md`, `DECISIONS.md`, and the latest entries in `UPDATES.jsonl`.
2. Claim one task by editing its task file and adding an update row.
3. Work only inside the task scope unless the board owner expands it.
4. Record decisions before relying on them.
5. Attach verification evidence before moving a task to `review` or `done`.

## Board Shape

- `TASKS.md`: board index and task status
- `lanes/`: Asana/Jira-style task lanes
- `tasks/`: one durable task packet per work item
- `GATES.md`: mandatory requirements and verification gates
- `DECISIONS.md`: Confluence-style decision log
- `UPDATES.jsonl`: append-only activity feed
- `HANDOFFS.md`: transfer notes between agents
- `AGENTS.md`: agent operating rules for this board
- `artifacts/`: plans, outputs, screenshots, logs, generated files
- `inbox/`: untriaged notes, imported context, pending requests
