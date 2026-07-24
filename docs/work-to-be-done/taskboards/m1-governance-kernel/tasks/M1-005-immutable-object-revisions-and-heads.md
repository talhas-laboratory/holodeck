# M1-005: Add immutable object revisions and heads

Status: backlog  
Gate: intake  
Depends on: M1-003, M1-004  
Scenarios: GS-002, supports GS-003

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement stable object IDs, immutable sequential revisions, supersession links,
content hashes, and an explicit current-head lookup.

## Observable acceptance

- Finalized revisions cannot be updated.
- Concurrent writers cannot create the same next revision.
- A correction creates a linked revision and advances the head atomically.

## Verification

- Immutability, concurrent revision allocation, and head-consistency tests.

## Non-goals

- Approval applicability or lifecycle transitions.
