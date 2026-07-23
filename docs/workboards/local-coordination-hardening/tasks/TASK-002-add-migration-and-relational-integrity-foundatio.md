# TASK-002-add-migration-and-relational-integrity-foundatio: Add migration and relational-integrity foundation

Status: done
Owner: cursor
Current gate: done

## Problem

The database cannot evolve safely and completion discovers claim ownership by JSON text matching.

## Scope

In:

- Numbered migration ledger and idempotent upgrade runner.
- Foreign keys, WAL, busy timeout, status checks, and relational `claims.run_id`.
- Exact indexed release of a run's active claims.
- Workspace-scoped task identity migration.

Out:

- Backup/import/export and event history.

## Acceptance Criteria

- A database from the current schema upgrades without data loss.
- New claims store `run_id` in a column and release uses that column only.
- Foreign-key violations and invalid status values are rejected.
- The same task ID is valid in two workspaces but not duplicated within one.

## Plan

- Define migration versioning and upgrade transaction rules.
- Migrate current tables and backfill claim ownership from legacy payloads.
- Update store queries and add migration/integrity tests.

## Verification Evidence

- `python -m pytest -q` → 63 passed (2026-07-23).
- `python -m compileall -q src tests` and `git diff --check` passed (2026-07-23).
- Migration `002` adds workspace FK, claim/run consistency trigger, active-path unique index, and reconciles all canonical-path overlaps before indexing, keeping the earliest active claim per workspace.
- Added migration coverage for exact duplicates, ancestor/descendant overlaps, and normalized run-path synchronization in `tests/test_hardening.py`.
- Changed artifacts: `src/holodeck/migrations.py`, `tests/test_hardening.py`.
- Residual risks: none known for legacy active-claim reconciliation.

## Updates

- Created: `2026-07-22T17:59:34.721997+00:00`

## Handoff Notes

- Dependency: TASK-001 establishes the SQLite transaction configuration.
- Implementation decisions: `DECISIONS.md` → **2026-07-23 — TASK-002 implementation decisions**.
