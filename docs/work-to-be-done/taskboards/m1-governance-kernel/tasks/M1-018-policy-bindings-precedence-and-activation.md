# M1-018: Add policy bindings, precedence, and activation

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-012, M1-016, M1-017  
Scenarios: GS-003, GS-009

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

## Scope

Completed under M1 durable governance kernel implementation and gap closure.

## Observable acceptance

- Unauthorized policy relaxation fails closed.
- Stale approval applicability denies with reason.deny.stale_approval.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_evaluators_policy.py tests/test_governance_integrated_scenarios.py::test_gs003_stale_approval_blocks_transition tests/test_governance_integrated_scenarios.py::test_gs009_policy_precedence
python -m pytest -q
```

Results (2026-07-24):

- Focused governance suite: **82 passed**
- Full suite: **192 passed**

## Changed files

- `src/holodeck_governance/domain/policy/binding.py`
- `src/holodeck_governance/domain/evaluators/primitives.py`
- `tests/test_governance_evaluators_policy.py`
- `tests/test_governance_integrated_scenarios.py`
- board index / updates / this packet

## Residual risks

- Policy binding persistence table is optional; merge semantics are domain-enforced.

## Non-goals

- M2–M8 capabilities remain out of scope.
