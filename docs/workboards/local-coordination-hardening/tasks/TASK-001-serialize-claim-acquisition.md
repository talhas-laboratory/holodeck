# TASK-001-serialize-claim-acquisition: Serialize claim acquisition

Status: done
Owner: cursor
Current gate: done

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

- `python -m pytest -q` → 25 passed (2026-07-23).
- Added `tests/test_hardening.py::test_concurrent_claims_allow_only_one_active_run`.
- Changed files: `src/holodeck_runtime/errors.py`, `src/holodeck_runtime/migrations.py`, `src/holodeck_runtime/store.py`.
- Residual risks: none known for TASK-001 scope.

## Updates

- Created: `2026-07-22T17:59:34.721889+00:00`

## Handoff Notes

- Dependency: none. This is the first implementation task.
- Implementation decisions: `DECISIONS.md` → **2026-07-23 — TASK-001 implementation decisions**.
