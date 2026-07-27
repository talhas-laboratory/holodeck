# M1-016: Add typed primitive registry and composition

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-007, M1-012–M1-015  
Scenarios: supports GS-003, GS-004, GS-008, GS-011

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

## Scope

Completed under M1 durable governance kernel implementation and gap closure.

## Observable acceptance

- Primitives include revision/transition/permission/approval/grant checks with composition ops.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_evaluators_policy.py
python -m pytest -q
```

Results (2026-07-24):

- Focused governance suite: **82 passed**
- Full suite: **192 passed**

## Changed files

- `src/holodeck_governance/domain/evaluators/primitives.py`
- `tests/test_governance_evaluators_policy.py`
- board index / updates / this packet

## Residual risks

- none known

## Non-goals

- M2–M8 capabilities remain out of scope.
