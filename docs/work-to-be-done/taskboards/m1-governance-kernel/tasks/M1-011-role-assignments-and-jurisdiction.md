# M1-011: Add role assignments and jurisdiction checks

Status: backlog  
Gate: intake  
Depends on: M1-010  
Scenarios: supports GS-001, GS-004, GS-009

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement immutable, effective-dated actor-to-role assignments scoped to tenant,
workspace, and declared jurisdiction.

## Observable acceptance

- Active in-scope assignments resolve; expired or out-of-scope assignments do not.
- No assignment can cross its tenant boundary.

## Verification

- Role assignment matrix with time and jurisdiction boundaries.

## Non-goals

- Per-object delegation or policy evaluation.
