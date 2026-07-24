# M1-006: Define legacy-import mapping and provenance

Status: backlog  
Gate: intake  
Depends on: M1-003, M1-004, M1-005  
Scenarios: GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Define the deterministic mapping from existing workspaces, tasks, runs, and
claims into tenant-bound M1 identifiers, revisions, and `legacy_import` status.

The contract must list every current task/run lifecycle value and assign a
one-way M1 mapping or explicit unsupported disposition. It may not silently
represent a legacy status as an M1-governed transition.

## Observable acceptance

- A fixture produces the same mapping on repeated dry runs.
- The mapping never fabricates actors, authority, approvals, evidence, or decisions.

## Verification

- Golden mapping fixture and unsupported/ambiguous legacy-data cases.

## Non-goals

- Executing the production migration; M1-023 owns that.
