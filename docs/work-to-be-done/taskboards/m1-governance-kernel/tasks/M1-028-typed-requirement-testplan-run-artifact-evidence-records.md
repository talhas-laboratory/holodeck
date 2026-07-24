# M1-028: Add typed requirement, test-plan, run, artifact, and evidence records

Status: backlog  
Gate: intake  
Depends on: M1-005, M1-007, M1-008, M1-027  
Scenarios: GS-002, GS-003, GS-006, GS-013, GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement typed relational contracts for `Requirement`, `TestPlan`, `Run`,
`Artifact`, and `Evidence`. Evidence stores immutable attributable metadata,
content hash, and external artifact reference; it never stores the artifact
body or claims M6 evidence-sufficiency behavior.

## Observable acceptance

- Each type is tenant-owned, typed, attributable, and revisioned or immutable
  according to its contract.
- A run targets an exact mission revision and has a typed execution state/result.
- Evidence and artifacts are hash-addressed metadata with explicit source and
  provenance references, not free-form mission-payload claims.

## Verification

- Schema/migration and immutability tests for all five types.
- Focused GS-002, GS-003, GS-006, GS-013, and GS-014 fixtures.

## Non-goals

- Generating requirements/test plans, launching runs, storing artifacts, or deciding evidence sufficiency.
