# M1-022: Add decision reconstruction query services

Status: done
Owner: implementation-agent  
Gate: done
Depends on: see TASKS.md  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- reconstruct_from_command is command-scoped for receipt/eval/events/transitions/outbox.
- DecisionRecord rows are returned (gov_decisions / subject links).
- HTTP reconstruction adapter exposes decisions.

## Observable acceptance

GS-013 asserts decisions; adapter returns decisions list.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_integrated_scenarios.py -k gs013
python -m pytest -q tests/test_governance_reconstruction_migration.py
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: DecisionRecord included in reconstruction after P0 fix; GS-013 tightened.

## Changed files

- `src/holodeck_governance/storage/sqlite/reconstruction.py`
- `src/holodeck_control_plane/governance_commands.py`
- `tests/test_governance_integrated_scenarios.py`

## Residual risks

- Graph population for edges/grants remains fixture/helper driven on some paths.
