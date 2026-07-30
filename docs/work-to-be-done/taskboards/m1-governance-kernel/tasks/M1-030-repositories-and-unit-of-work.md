# M1-030: Implement repositories and unit-of-work transaction boundary

Status: done
Owner: implementation-agent  
Gate: done
Depends on: see TASKS.md  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: GS-010

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- SqliteUnitOfWork atomic commit with fault injection.
- Head mutations re-read under BEGIN IMMEDIATE.
- Numbered migrations own schema; repos cover command/record/edge/authority/policy.

## Observable acceptance

UoW fault injection + contention under IMMEDIATE + migrations v1–v6.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_lifecycle_uow.py tests/test_governance_p1_enforcement.py -k competing
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: UoW atomicity + contention head re-read proofs.

## Changed files

- `src/holodeck_governance/storage/sqlite/uow.py`
- `src/holodeck_governance/storage/sqlite/migrations.py`
- `src/holodeck_governance/storage/sqlite/tasks.py`
- `src/holodeck_governance/storage/sqlite/runs.py`

## Residual risks

- Private revision helpers still used by some seed/repo paths.
