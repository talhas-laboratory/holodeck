# Implementation roadmap and dependency order

| Phase | Deliverable | Exit condition |
| --- | --- | --- |
| A | Shared records, work graph, schema-versioned APIs/events | Explain why a task exists, what must be true, and which revision is under discussion. |
| B | Workspace model, sources, modules, approvals, curators | Onboarding and task creation produce reviewable project/task models. |
| C | Precedence-aware role packets, hashes, previews, expansion | Each role gets a reproducible immutable packet. |
| D | Requirements, TestPlan, evidence coverage, gate reports | Tasks cannot begin or complete without meaning and evidence plans. |
| E | Trace, worklogs, completion/interruption protocol | Distinguish facts, claims, and unverified assertions. |
| F | One controlled CLI adapter, incremental adapters, CI gate | One agent can be launched/observed/prevented from self-completing. |
| G | Review packets, findings, responses, re-review, escalation | Worker/reviewer cycles preserve history and alignment. |
| H | Independent tests, holdouts, verification decisions, promotion | Acceptance is evidence-based and experience improves future work. |

## Avoid premature complexity

Use typed relational edges before a graph database; explicit sources/module tags/deterministic selection before a vector database; deterministic paths for narrow high-confidence work; no authoritative generated summaries; and no unrestricted multi-agent debate before role, finding, and escalation mechanics exist.
