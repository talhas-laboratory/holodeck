# M1-029: Add typed review, approval, decision, and escalation records

Status: backlog  
Gate: intake  
Depends on: M1-005, M1-007, M1-008, M1-010  
Scenarios: GS-002, GS-003, GS-004, GS-011, GS-012, GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement immutable typed records for `Review`, `Approval`, `Decision`, and
`Escalation`, with actor/role attribution, exact subject revision references,
provenance, and authoritative timestamps. These are vocabulary and audit
primitives only; richer review and acceptance policy remain later work.

## Observable acceptance

- An approval/review/decision identifies the actor, role/grant, exact subject
  revision, applicable policy/evaluator references, and immutable reason.
- A decision is distinct from its announcing event; an escalation is distinct
  from changing the governing decision.
- A later subject revision neither mutates an older approval nor makes it apply
  implicitly to newer work.

## Verification

- Immutability, attribution, exact-revision, and tenant-isolation tests.
- Focused GS-002, GS-003, GS-004, GS-011, GS-012, and GS-013 fixtures.

## Non-goals

- Full M6 acceptance semantics, human collaboration adapters, or notification delivery.
