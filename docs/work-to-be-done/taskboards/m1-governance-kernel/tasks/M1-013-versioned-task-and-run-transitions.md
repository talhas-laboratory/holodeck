# M1-013: Add versioned task and run transition definitions

Status: done
Owner: implementation-agent  
Gate: done
Depends on: see TASKS.md  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: GS-006, GS-010

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Accepted task/run transitions mutate heads via apply_transition under UoW.
- run.transition requires transition_run permission (no task-permission fallback).
- Invalid transitions leave no success effects.

## Observable acceptance

task.transition and run.transition mutate gov_tasks/gov_runs + heads; permission narrowing covered.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_commands.py tests/test_governance_p1_enforcement.py -k 'run_transition or competing or transition'
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Run path + DecisionRecord + permission narrowing and contention proofs in p1 suite.

## Changed files

- `src/holodeck_governance/domain/lifecycle.py`
- `src/holodeck_governance/storage/sqlite/tasks.py`
- `src/holodeck_governance/storage/sqlite/runs.py`
- `src/holodeck_governance/storage/sqlite/command_service.py`

## Residual risks

- Broader run lifecycle states beyond created→active remain thin.
