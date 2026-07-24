# M1-023: Execute legacy migration and compatibility tests

Status: backlog  
Gate: intake  
Depends on: M1-006, M1-013, M1-014, M1-015, M1-016, M1-017, M1-018, M1-019, M1-020, M1-021, M1-022  
Scenarios: GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement the additive current-SQLite-to-M1 migration and retain documented
legacy API behavior through the compatibility seam.

## Observable acceptance

- Representative IDs, timestamps, task/run/claim behavior, and records survive.
- Imported data has explicit legacy provenance and no fabricated governance claims.

## Verification

- Fresh install, every supported upgrade path, rollback-on-failure, and API regression suite.

## Non-goals

- Retiring legacy endpoints.
