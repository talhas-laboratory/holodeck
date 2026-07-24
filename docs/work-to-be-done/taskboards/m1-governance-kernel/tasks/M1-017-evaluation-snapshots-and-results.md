# M1-017: Add evaluation snapshots and results

Status: backlog  
Gate: intake  
Depends on: M1-016  
Scenarios: GS-008, supports GS-003, GS-010, GS-011, GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Persist immutable exact-revision input snapshots, primitive outcomes, evaluator
contract/digest, reason codes, and final governance outcome.

## Observable acceptance

- Later role, source, policy, or subject changes cannot alter a stored result.
- Missing or stale input cannot produce `allow`.

## Verification

- Snapshot replay and fail-closed fixtures for GS-008.

## Non-goals

- Policy precedence or domain-state mutation.
