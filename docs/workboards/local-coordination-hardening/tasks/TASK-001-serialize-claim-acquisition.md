# TASK-001-serialize-claim-acquisition: Serialize claim acquisition

Status: backlog
Owner: unassigned
Current gate: intake

## Problem

Two concurrent deferred SQLite transactions can both observe no active claim and create overlapping work.

## Scope

In:

- Explicit serialized claim transaction with bounded lock handling.
- Component-based overlap check on the current stored claim form.
- Deterministic competing-connection regression test.

Out:

- Path canonicalization and schema migrations (separate tasks).

## Acceptance Criteria

- Two simultaneous attempts to claim the same path yield exactly one active run.
- Parent/child paths conflict (`src` and `src/api.py`).
- Lock exhaustion is surfaced as a domain error suitable for HTTP `503`.

## Plan

- Configure explicit SQLite transaction behavior and busy timeout.
- Acquire `BEGIN IMMEDIATE`, read active claims, validate, insert run and claims, commit or roll back.
- Add a barrier-based concurrency test.

## Verification Evidence

- Not run yet. Planned: `python -m pytest -q`.

## Updates

- Created: `2026-07-22T17:59:34.721889+00:00`

## Handoff Notes

- Dependency: none. This is the first implementation task.
