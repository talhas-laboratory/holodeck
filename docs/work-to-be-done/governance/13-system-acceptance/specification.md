# 13. Definition of done and system-level acceptance criteria

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 13. Definition of done and system-level acceptance criteria

The improvement program is not complete because individual screens or tables exist. The following system-level behaviors must work together.

### 13.1 Workspace and context

- A user can inspect and revise a versioned model of project purpose, users, architecture, principles, sources, and gaps.
- A task is linked to its parent work, affected users, dependencies, scope, non-goals, and invariants.
- A worker, test planner, and reviewer receive different immutable context packets with complete provenance.
- Context changes never silently alter an active run.
### 13.2 Requirements and tests

- Every critical requirement has a source, rationale, scenarios, acceptance conditions, and required evidence.
- The test planner produces explicit failure hypotheses, boundaries, oracles, layers, and coverage.
- Independent tests can be generated without first reading the worker’s reasoning.
- Evidence coverage is evaluated per requirement rather than by generic suite status alone.
### 13.3 Work evidence and enforcement

- Holodeck automatically records observable work through an adapter.
- The worker submits a structured completion candidate and cannot directly set accepted completion.
- Claims in the completion candidate are checked against traces and repository evidence.
- Interrupted runs produce recoverable summaries.
- Protected merge/release can be blocked when records or evidence are insufficient.
### 13.4 Review

- Reviewers know why the task matters and what surrounding systems must be preserved.
- Reviews attach to exact immutable candidate revisions.
- Findings are structured, anchored, evidence-linked, jurisdiction-aware, and dispositioned explicitly.
- Workers respond per finding and reviewers re-review exact deltas.
- Disagreements and scope gaps follow bounded escalation paths.
### 13.5 Learning

- Observed facts, agent interpretations, and validated knowledge remain distinct.
- Validated failures create regression and recovery candidates.
- Knowledge promotion is versioned, source-linked, and can be disputed or superseded.
- Future context selection can retrieve validated history without treating raw worklogs as authority.
### 13.6 Ultimate product test

```text
End-state criterion
For any accepted change, Holodeck must be able to answer: Why did this task exist? What requirements applied? What context did each agent receive? What did the worker actually do? What failed and how was it recovered? What did reviewers find? What changed in response? Which independent evidence proved the requirements? Who or what authorized acceptance? What validated learning was retained?
```
