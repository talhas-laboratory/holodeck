# M1-009: Add typed traceability edges

Status: backlog  
Gate: intake  
Depends on: M1-003, M1-004, M1-005, M1-007  
Scenarios: GS-005, supports GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement the edge-type registry and immutable revision-to-revision edges with
actor, time, provenance, and endpoint constraints.

Use the typed governance-object registry and allowed-edge-type matrix defined
in the M1 design. SQLite enforces endpoint existence and tenant match with
foreign keys; a tested trigger or same-boundary domain validation enforces type
compatibility.

## Observable acceptance

- Missing, incompatible, and cross-tenant endpoints are rejected.
- Valid supersession and evidence-support edges are traversable.

## Verification

- Complete edge compatibility matrix and traversal fixture for GS-005.

## Non-goals

- Graph database adoption or unrestricted custom edge types.
