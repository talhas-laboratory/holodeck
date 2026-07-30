# M1-028: Add typed requirement, test-plan, run, artifact, and evidence records

Status: done
Owner: implementation-agent  
Gate: done
Depends on: see TASKS.md  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: supports GS-006

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Typed record families persist via write repos + migration v5/v6.
- Run heads support run.transition command path.

## Observable acceptance

Record family write/reload + run transition persistence covered.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_grants_edges_records.py tests/test_governance_p1_enforcement.py -k 'run_transition or record'
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Write repos + run.transition DecisionRecord path verified.

## Changed files

- `src/holodeck_governance/storage/sqlite/records.py`
- `src/holodeck_governance/storage/sqlite/runs.py`
- `src/holodeck_governance/storage/sqlite/migrate_v5.py`
- `src/holodeck_governance/storage/sqlite/migrate_v6.py`

## Residual risks

- Record creates are repository APIs pending command-typed create envelopes.
