# M1 durable governance kernel

Purpose: implement M1 from the approved design without conflating it with later
collaboration, intelligence, execution, evidence-sufficiency, or review work.

Board id: `m1-governance-kernel`  
Owner: `talha`  
Status: planning complete; fresh-builder handoff pending M1-026  
Design: [`2026-07-24-m1-durable-governance-kernel-design.md`](../../../plans/2026-07-24-m1-durable-governance-kernel-design.md)
Test specification: [`2026-07-24-m1-governance-test-specification.md`](../../../plans/2026-07-24-m1-governance-test-specification.md)

The board contains 31 atomic, dependency-ordered packets. Each implementation
packet declares its governance scenarios and one observable verification target.

## Agent start protocol

1. Read `BUILDER_BASELINE.md`, the design, `TASKS.md`, `GATES.md`, `DECISIONS.md`, and recent updates.
2. Claim one ready task and update its packet plus `UPDATES.jsonl`.
3. Do not expand into M2–M8 without an explicit board decision.
4. Preserve user worktree changes and migrate existing records additively. Do not treat the current dirty worktree as an accepted M1 baseline.
5. Do not move a task to done without the recorded verification evidence.

## Board shape

- `TASKS.md` is the task index and current board state.
- `tasks/` contains one self-contained packet per implementation task.
- `DECISIONS.md` is the durable M1 decision log.
- `GATES.md` is mandatory for every task.
- `UPDATES.jsonl` is append-only activity history.
- `HANDOFFS.md` records transfer context when work pauses.
- `BUILDER_BASELINE.md` states the runnable baseline, current uncommitted inputs, and compatibility decisions a fresh builder must preserve.

## Milestone boundary

M1 establishes governance primitives. External collaboration ingestion, agent
launching, sandbox enforcement, automatic requirement/test generation, and full
acceptance evaluation are explicitly deferred.
