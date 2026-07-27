# M1-017: Add evaluation snapshots and results

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-016  
Scenarios: GS-008

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

## Scope

Completed under M1 durable governance kernel implementation and gap closure.

## Observable acceptance

- Command path persists evaluation snapshots/results and reconstruction can reload them.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_evaluators_policy.py tests/test_governance_integrated_scenarios.py::test_gs008_evaluation_reproducibility_via_command
python -m pytest -q
```

Results (2026-07-24):

- Focused governance suite: **82 passed**
- Full suite: **192 passed**

## Changed files

- `src/holodeck_governance/domain/evaluation/`
- `src/holodeck_governance/domain/evaluators/task_transition.py`
- `src/holodeck_governance/storage/sqlite/command_service.py`
- `tests/test_governance_evaluators_policy.py`
- `tests/test_governance_integrated_scenarios.py`
- board index / updates / this packet

## Residual risks

- none known

## Non-goals

- M2–M8 capabilities remain out of scope.
