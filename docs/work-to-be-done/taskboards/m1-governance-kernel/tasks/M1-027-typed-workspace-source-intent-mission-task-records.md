# M1-027: Add typed workspace, source, intent, mission, and task records

Status: backlog  
Gate: intake  
Depends on: M1-003, M1-004, M1-005, M1-007, M1-008  
Scenarios: GS-001, GS-002, GS-003, GS-013, GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement canonical typed relational records for `Workspace`, `Source`,
`Intent`, `Mission`, and `Task`, including shared governance metadata, tenant
ownership, revision/head behavior where applicable, provenance links, and
repository contracts. Preserve current workspace/task records through the
legacy-import seam rather than silently reclassifying them.

## Observable acceptance

- Each type has a relational contract, tenant ownership, opaque ID, required
  governance metadata, and appropriate immutable revision/head behavior.
- A mission/task links to workspace, source, and intent through relational
  references rather than opaque JSON.
- Cross-tenant references fail; imported records retain provenance and source
  IDs/timestamps when available.

## Verification

- Schema/migration tests for all five types.
- Focused GS-001, GS-002, GS-003, GS-013, and GS-014 fixtures.

## Non-goals

- Context compilation, collaboration ingress, rich interpretation, or automatic task creation.
