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

- `python -m pytest -q` → 60 passed (2026-07-23).
- Migration `002` adds workspace FK, claim/run consistency trigger, active-path unique index, and reconciles legacy duplicate active claims before indexing.
- Added `test_migration_two_reconciles_duplicate_active_claims` and related integrity coverage in `tests/test_hardening.py`.
- Residual risks: overlapping (non-identical) active paths from pre-hardening data are not auto-reconciled; only exact duplicate paths are released during migration.

## Updates

- Created: `2026-07-22T17:59:34.721997+00:00`

## Handoff Notes

- Dependency: TASK-001 establishes the SQLite transaction configuration.
- Implementation decisions: `DECISIONS.md` → **2026-07-23 — TASK-002 implementation decisions**.
