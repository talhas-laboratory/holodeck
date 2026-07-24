# M1-026: Establish fresh-builder baseline and compatibility contract

Status: ready  
Gate: readiness

## Scope

Make the M1 starting point reproducible without modifying unrelated user work.
Record the accepted baseline/snapshot, supported bootstrap command, current
runtime inventory, and implementation decisions for Python 3.11 UUIDv7
compatibility, legacy lifecycle imports, and SQLite typed-edge enforcement.

## Observable acceptance

- A fresh checkout installs and runs the suite with one documented command sequence.
- The exact baseline commit or user-approved snapshot is recorded before schema work.
- Every current task/run lifecycle value has a documented import disposition.
- UUID generation and typed-edge enforcement have a named, testable approach.

## Verification

- `python -m pip install -e ".[dev]" && python -m pytest -q`
- Review `BUILDER_BASELINE.md`, `HANDOFFS.md`, and M1-006/M1-009 tests.

## Non-goals

- Committing, discarding, or otherwise changing unrelated worktree changes.
- Implementing M1 schemas, UUID generation, lifecycle mapping, or edges.

