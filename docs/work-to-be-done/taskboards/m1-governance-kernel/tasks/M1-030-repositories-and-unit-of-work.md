# M1-030: Implement repositories and unit-of-work transaction boundary

Status: backlog  
Gate: intake  
Depends on: M1-003, M1-004, M1-005, M1-008, M1-027, M1-028, M1-029  
Scenarios: GS-007, GS-010, GS-011, supports GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement domain-owned repository interfaces and a storage-backed unit of work.
Application command handlers use this boundary for all governed persistence.
The unit of work is the only path allowed to atomically commit record heads,
command receipts, evaluation results, transitions, events, and outbox rows.

## Observable acceptance

- Domain/application code depends on repository interfaces, never SQLite or adapter types.
- An injected fault leaves either the complete allowed-command write set or no success write set.
- Direct adapter/store mutation cannot bypass the governed command path for M1 records.

## Verification

- Architecture dependency test and transactional fault-injection tests.
- Focused GS-007, GS-010, GS-011, and reconstruction-support fixtures.

## Non-goals

- Distributed transactions, event sourcing, or replacing the legacy store in one rewrite.
