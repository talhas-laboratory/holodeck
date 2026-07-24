# M1-014: Add command envelopes and immutable receipts

Status: backlog  
Gate: intake  
Depends on: M1-005, M1-010, M1-011, M1-012, M1-013  
Scenarios: GS-011, supports GS-001, GS-003, GS-006, GS-010

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement validated command envelopes and immutable receipts for accepted,
denied, malformed, stale, and unauthorized outcomes.

## Observable acceptance

- All mutation adapters call one command boundary.
- A rejected command leaves its receipt while producing no subject transition.

## Verification

- GS-011 rejection table and an architecture test preventing adapter-to-store writes.

## Non-goals

- Deduplication, evaluator logic, or event publication.
