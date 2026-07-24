# M1-002: Governance test specification

Status: backlog  
Gate: intake

## Scope

Turn M1 invariants into reusable primitive, evaluator-contract, and end-to-end
governance scenarios before schema and command implementation begins.

## Inputs

- [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)
- [M1 design](../../../../plans/2026-07-24-m1-durable-governance-kernel-design.md)
- Current runtime inventory in [M1-001](M1-001-kernel-vocabulary-and-module-contracts.md)

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

- Scenario catalogue review against every M1 design decision and current M0
  regression suite.

## Non-goals

- Implementing the kernel or defining M4/M6 evidence-sufficiency behavior.
