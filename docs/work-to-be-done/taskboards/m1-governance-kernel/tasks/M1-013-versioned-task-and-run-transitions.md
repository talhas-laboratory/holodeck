# M1-013: Add versioned task and run transition definitions

Status: backlog  
Gate: intake  
Depends on: M1-005, M1-010, M1-011, M1-012  
Scenarios: GS-006

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement kernel-owned versioned transition definitions for the agreed minimal
task and run states plus append-only transition records.

## Observable acceptance

- Every allowed edge succeeds under its definition version.
- Every undocumented edge fails without changing subject state.

## Verification

- Complete transition matrices and coexistence test for two definition versions.

## Non-goals

- Review, verification, release, or workspace-editable state machines.
