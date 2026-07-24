# M1-031: Define domain-error, reason-code, and event-schema catalogs

Status: backlog  
Gate: intake  
Depends on: M1-001  
Scenarios: GS-001–GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Publish versioned, machine-readable catalogs for domain errors, evaluator reason
codes, event types, and event payload schemas. Define ownership, compatibility,
and adapter mappings. The catalog constrains implementation; it is not a
free-form configuration mechanism.

## Observable acceptance

- Every governance scenario names expected catalog identifiers and payload versions.
- Errors distinguish invalid transition, stale revision, missing authority,
  cross-tenant access, malformed command, idempotency conflict, and incomplete
  evaluation without parsing message text.
- Event schemas identify immutable causal metadata and allowed payload fields.

## Verification

- Catalog validation tests, evaluator-contract fixture snapshots, and
  scenario-to-catalog coverage check.

## Non-goals

- Implementing every event ledger table or delivery worker; M1-019 through
  M1-021 implement those consumers.

