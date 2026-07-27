# M1-002: Governance test specification

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-001, M1-031

## Scope

Turn M1 invariants into reusable primitive, evaluator-contract, and end-to-end
governance scenarios before schema and command implementation begins.

## Inputs

- [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)
- [M1 design](../../../../plans/2026-07-24-m1-durable-governance-kernel-design.md)
- Current runtime inventory in [M1-001](M1-001-kernel-vocabulary-and-module-contracts.md)
- Catalogs from [M1-031](M1-031-domain-error-reason-event-catalogs.md)

## Acceptance criteria

- Every locked M1 invariant maps to a scenario ID and test layer.
- Scenarios assert both required audit records and forbidden side effects.
- Canonical fixture builders, concurrency setup, migration fixtures, and exact
  reason-code/event expectations are defined.
- Every implementation packet that changes governed behavior references this
  specification and declares owned scenarios.

## Observable acceptance

- Each locked M1 invariant has a scenario owner, exact catalog identifiers, and
  absence assertions for rejected commands.
- Fixture builders and transactional fault points are concrete enough for a
  fresh agent to add tests without inventing acceptance criteria.
- Every implementation packet traces its verification to one or more scenarios
  or explicitly records why it is infrastructure-only.

## Verification

```bash
python -m pytest -q tests/test_governance_scenario_spec.py tests/test_governance_catalogs.py
python -m pytest -q
```

Results: scenario-spec **4 passed**; catalogs covered; full suite after closeout.

## Changed files

- `docs/plans/2026-07-24-m1-governance-test-specification.md`
- `src/holodeck_governance/testing/__init__.py`
- `tests/test_governance_scenario_spec.py`
- this packet / TASKS / UPDATES

## Residual risks

- Fixture builders are contract-level until repositories exist; GS tests remain
  pending their owning packets.
- none known for specification scope

## Non-goals

- Implementing the kernel or defining M4/M6 evidence-sufficiency behavior.
