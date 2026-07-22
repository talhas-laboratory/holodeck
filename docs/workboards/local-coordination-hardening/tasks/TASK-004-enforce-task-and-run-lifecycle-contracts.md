# TASK-004-enforce-task-and-run-lifecycle-contracts: Enforce task and run lifecycle contracts

Status: backlog
Owner: unassigned
Current gate: intake

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

- Not run yet. Planned: `python -m pytest -q` with transition matrices.

## Updates

- Created: `2026-07-22T17:59:34.722201+00:00`

## Handoff Notes

- Dependency: TASK-002 establishes scoped task identity and relational ownership.
