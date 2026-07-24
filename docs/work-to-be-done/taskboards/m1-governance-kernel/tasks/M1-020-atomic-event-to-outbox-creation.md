# M1-020: Add atomic event-to-outbox creation

Status: backlog  
Gate: intake  
Depends on: M1-019  
Scenarios: GS-010, supports GS-011

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Create adapter-neutral outbox obligations in the same transaction as permitted
transition, receipt, evaluation, and domain event.

## Observable acceptance

- Fault injection at every write boundary commits the complete success set or none.
- Rejected commands produce no success event or success outbox item.

## Verification

- GS-010 boundary-failure matrix and GS-011 absence assertions.

## Non-goals

- Claiming, delivering, retrying, or provider formatting.
