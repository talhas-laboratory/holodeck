# M1-018: Add policy bindings, precedence, and activation

Status: backlog  
Gate: intake  
Depends on: M1-012, M1-016, M1-017  
Scenarios: GS-003, GS-009

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement versioned tenant/workspace policy bindings, evaluator-declared safe
merge rules, activation decisions, and scoped expiring object exceptions.

## Observable acceptance

- Lower scope tightens or safely merges; unauthorized relaxation fails.
- New activation affects future evaluations while historical results retain old bindings.

## Verification

- GS-003 and GS-009 precedence, activation, and exact-revision approval fixtures.

## Non-goals

- General policy language or M4/M6 acceptance semantics.
