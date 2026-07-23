# TASK-004-enforce-task-and-run-lifecycle-contracts: Enforce task and run lifecycle contracts

Status: done
Owner: cursor
Current gate: done

## Problem

Tasks and runs accept arbitrary or contradictory statuses, weakening coordination semantics.

## Scope

In:

- Workspace-scoped task lookup behavior.
- Explicit task and run status domains and transition validators.
- Terminal run completion with atomic claim release.

Out:

- Scheduler-driven queued-run activation and approval workflows.

## Acceptance Criteria

- Unsupported statuses are rejected.
- Illegal state transitions are rejected without modifying data.
- Completing a run accepts only terminal outcomes and releases its claims once.
- Existing lifecycle API behavior remains compatible for the default happy path.

## Plan

- Define transition maps in a dependency-free domain module.
- Apply validators in store mutations.
- Add transition-matrix and multi-workspace identity tests.

## Verification Evidence

- `python -m pytest -q` → 25 passed (2026-07-23).
- Added lifecycle tests in `tests/test_hardening.py`; updated `tests/test_store.py` for legal transitions.
- Changed files: `src/holodeck_runtime/lifecycle.py`, `src/holodeck_runtime/store.py`, `src/holodeck_runtime/service.py`.
- Residual risks: none known for TASK-004 scope.

## Updates

- Created: `2026-07-22T17:59:34.722201+00:00`

## Handoff Notes

- Dependency: TASK-002 establishes scoped task identity and relational ownership.
- Implementation decisions: `DECISIONS.md` → **2026-07-23 — TASK-004 implementation decisions**.
