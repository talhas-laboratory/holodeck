# TASK-003-canonicalize-and-enforce-claim-paths: Canonicalize and enforce claim paths

Status: done
Owner: cursor
Current gate: done

## Problem

Raw string-prefix path comparison allows equivalent, escaping, and out-of-bound paths to bypass coordination.

## Scope

In:

- Canonical logical repository-relative POSIX path validator.
- Artifact-root and `scope_out` validation using canonical components.
- Normalized component overlap checks and regression tests.

Out:

- Resolving symlinks or filesystem case behavior without a verified repository-root adapter.

## Acceptance Criteria

- Absolute, escaping, empty, and backslash-ambiguous claim paths are rejected.
- Equivalent valid spellings normalize to one identity.
- Claims must fall under an artifact root and not intersect scope-out paths.
- Ancestor/descendant overlaps are rejected after normalization.

## Plan

- Specify the logical path grammar and normalization rules.
- Normalize workspace boundaries and claims through one validator.
- Replace string-prefix overlap code and add table-driven tests.

## Verification Evidence

- `python -m pytest -q` → 25 passed (2026-07-23).
- Added path table tests in `tests/test_hardening.py`.
- Changed files: `src/holodeck_runtime/paths.py`, `src/holodeck_runtime/store.py`.
- Residual risks: none known for TASK-003 scope.

## Updates

- Created: `2026-07-22T17:59:34.722099+00:00`

## Handoff Notes

- Dependency: TASK-002 supplies the durable schema contract.
- Implementation decisions: `DECISIONS.md` → **2026-07-23 — TASK-003 implementation decisions**.
