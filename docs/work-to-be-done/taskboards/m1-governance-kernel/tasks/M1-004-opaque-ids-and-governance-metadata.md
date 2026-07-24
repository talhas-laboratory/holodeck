# M1-004: Add opaque IDs and shared governance metadata

Status: backlog  
Gate: intake  
Depends on: M1-001, M1-002  
Scenarios: supports GS-002 and GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement UUIDv7-style internal IDs and the shared tenant, schema-version,
actor, provenance, and UTC timestamp metadata contract.

Use the Python-3.11-compatible generator selected in M1-026; do not depend on
an unavailable standard-library UUIDv7 API or introduce a runtime dependency
without an explicit board decision.

## Observable acceptance

- IDs are opaque, unique, and independent from labels or external identifiers.
- Shared metadata validates identically across representative record types.

## Verification

- ID uniqueness/format tests and metadata contract tests with a fixed clock.

## Non-goals

- Revision persistence or external-reference storage.
