# M1-026: Establish fresh-builder baseline and compatibility contract

Status: done  
Owner: implementation-agent  
Gate: done  
Scenarios: see TASKS.md / PACKET_SCENARIO_OWNERS

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)
Depends on: —


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

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

## Contract (readiness)

- Baseline identity is a git commit SHA, not planning-document freshness.
- Compatibility decisions are named with owning packets; this task does not
  implement them.
- Legacy thin-slice mission/acceptance/evidence tables are migration inputs
  with explicit unsupported-as-M1-governance disposition.

## Implementation notes

Documentation-only. Updated `BUILDER_BASELINE.md` and `HANDOFFS.md`. No schema
or runtime code changes.

## Verification

Commands:

```bash
git rev-parse HEAD
git status --short
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

Results:

- HEAD: `0adbc1c344ce7f743a6f5ece37501fb096e432d8`
- Worktree: clean
- Pytest: **110 passed** in ~29.6s (Python 3.13.7)

## Changed files

- `docs/work-to-be-done/taskboards/m1-governance-kernel/BUILDER_BASELINE.md`
- `docs/work-to-be-done/taskboards/m1-governance-kernel/HANDOFFS.md`
- `docs/work-to-be-done/taskboards/m1-governance-kernel/tasks/M1-026-fresh-builder-baseline-and-compatibility.md`
- `docs/work-to-be-done/taskboards/m1-governance-kernel/TASKS.md`
- `docs/work-to-be-done/taskboards/m1-governance-kernel/UPDATES.jsonl`
- `docs/work-to-be-done/taskboards/m1-governance-kernel/README.md`

## Residual risks

- Baseline was recorded on Python 3.13.7; package requires `>=3.11`. A 3.11 CI
  matrix is not yet proven by this packet (none known for M1-026 scope).
- Legacy→M1 status mapping is documented here for builder guidance; M1-006 must
  still publish the authoritative golden fixture before M1-023 migration.

## Non-goals

- Committing, discarding, or otherwise changing unrelated worktree changes.
- Implementing M1 schemas, UUID generation, lifecycle mapping, or edges.
