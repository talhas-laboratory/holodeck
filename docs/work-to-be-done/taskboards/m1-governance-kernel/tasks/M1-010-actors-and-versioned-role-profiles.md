# M1-010: Add actors and versioned role profiles

Status: backlog  
Gate: intake  
Depends on: M1-003, M1-004, M1-005  
Scenarios: foundation for GS-003, GS-004, GS-009

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement tenant-bound human, agent, service, and import actors plus immutable
role-profile revisions containing permissions and jurisdiction contracts.

## Observable acceptance

- Actors and roles remain distinct records.
- A role revision can be reconstructed after a newer revision is activated.

## Verification

- Actor-type and role-revision contract tests.

## Non-goals

- Assigning roles, delegating authority, or mapping external identities.
