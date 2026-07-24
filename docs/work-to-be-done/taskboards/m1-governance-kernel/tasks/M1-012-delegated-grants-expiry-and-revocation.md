# M1-012: Add delegated grants, expiry, and revocation

Status: backlog  
Gate: intake  
Depends on: M1-005, M1-010, M1-011  
Scenarios: GS-004, supports GS-003 and GS-009

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement exact-revision object grants with delegator, recipient, actions,
scope, effective period, re-delegation flag, and separate revocation decision.

## Observable acceptance

- Only active, in-scope, unrevoked grants authorize their declared actions.
- Self-expansion and unauthorized re-delegation fail.

## Verification

- GS-004 matrix for active, expired, revoked, wrong-revision, and wrong-scope grants.

## Non-goals

- Full command evaluation or external approvals.
