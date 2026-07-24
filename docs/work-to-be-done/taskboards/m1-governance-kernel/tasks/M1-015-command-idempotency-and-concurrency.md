# M1-015: Add command idempotency and concurrency control

Status: backlog  
Gate: intake  
Depends on: M1-014  
Scenarios: GS-007, supports GS-010 and GS-011

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement semantic payload hashing, idempotency-key reservation, original-result
return, conflict detection, and optimistic expected-revision checks.

## Observable acceptance

- Exact retries return one original result and create no duplicates.
- Concurrent changed-payload or stale-revision attempts produce stable conflicts.

## Verification

- Multi-connection GS-007 race and retry tests.

## Non-goals

- Evaluator decisions or external event deduplication.
