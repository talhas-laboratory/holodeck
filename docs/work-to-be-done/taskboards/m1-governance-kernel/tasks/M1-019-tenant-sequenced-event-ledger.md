# M1-019: Add tenant-sequenced domain event ledger

Status: backlog  
Gate: intake  
Depends on: M1-014, M1-015, M1-016, M1-017, M1-018  
Scenarios: supports GS-010, GS-011, GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement immutable domain events with UUIDv7 IDs, tenant-local transactional
sequence, actor, subjects, causation, correlation, and schema-versioned payload.

## Observable acceptance

- Concurrent events receive unique deterministic tenant sequence positions.
- Stored events cannot be mutated or deleted through application commands.

## Verification

- Concurrent sequence allocation, causality, and immutability tests.

## Non-goals

- External delivery or full event sourcing.
