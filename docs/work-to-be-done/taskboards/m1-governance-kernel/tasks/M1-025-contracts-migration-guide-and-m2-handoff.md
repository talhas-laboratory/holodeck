# M1-025: Publish contracts, migration guide, and M2 handoff

Status: review
Owner: implementation-agent  
Gate: review
Depends on: see TASKS.md  
Held: 2026-07-24 release-blocking run 7; milestone not human-accepted  
Scenarios: milestone handoff

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Contracts/migration/M2 handoff artifact published after M1-024 evidence.
- Artifact reflects enforced-kernel + release-blocking run 7 contracts (v7,
  application seam, approval cardinality, envelopes).
- Milestone remains human-accepted separately (not auto-closed).

## Observable acceptance

Artifact present; documents migrations v1–v7, application composition seam,
command boundary decision, deferred M2.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
test -f docs/work-to-be-done/taskboards/m1-governance-kernel/artifacts/m1-contracts-migration-m2-handoff.md
python -m pytest -q
```

Result: **252 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Artifact refreshed for run 9 (schema v9 / M1-033); held in review with M1-024.

## Changed files

- `docs/work-to-be-done/taskboards/m1-governance-kernel/artifacts/m1-contracts-migration-m2-handoff.md`
- `docs/work-to-be-done/taskboards/m1-governance-kernel/artifacts/m1-module-contracts.md`

## Residual risks

- Milestone not accepted; commit/packaging hygiene called out by review remains
  a release process item, not an auto-close gate.
