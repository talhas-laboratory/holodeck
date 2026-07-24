# M1 governance test specification

**Status:** Approved test-design deliverable  
**Milestone:** M1 — Durable governance kernel  
**Companion task:** [`M1-002`](../work-to-be-done/taskboards/m1-governance-kernel/tasks/M1-002-governance-test-specification.md)

## Purpose

M1 is valuable only if its system-wide governance guarantees hold across command
handling, authority, persistence, evaluation, event recording, and delivery
recovery. This specification defines those guarantees as executable acceptance
scenarios before their components are implemented.

Component tests do not replace these scenarios. A component is not complete
until its relevant governance scenarios pass.

## Scenario contract

Every scenario must state:

```text
initial state
actors, roles, grants, and authority
policy/evaluator and exact revisions
command submitted
expected evaluation and reason codes
expected subject-state changes
expected events and outbox items
expected absence of unauthorized changes
reconstruction expectations
```

`M1-031` publishes the canonical domain-error, evaluator-reason-code, and
event-schema identifiers before this specification is marked implementation
ready. Scenario fixtures must assert those identifiers and payload versions,
not merely human-readable messages.

For a rejected command, test both facts:

- A command receipt and evaluation result exist where required.
- No governed transition, success event, or success outbox delivery was created.

## Test layers

| Layer | Purpose | Required evidence |
| --- | --- | --- |
| Primitive | Prove one typed rule has correct semantics. | Inputs, structured result, reason code. |
| Evaluator contract | Prove a code-defined evaluator against an immutable snapshot. | Primitive outcomes, policy binding, final outcome. |
| Governance scenario | Prove the complete transaction and audit path. | State, receipt, evaluation, event/outbox, and reconstruction result. |

No test layer may assume a later-milestone capability is already enforced. M1
tests generic transition, authority, policy, audit, and delivery mechanics;
M4/M6 define rich requirements, evidence sufficiency, and acceptance semantics.

## Canonical fixture world

Use composable fixture builders around a small deterministic world, not one
large mutable fixture:

```text
Tenant Alpha; Tenant Beta
Workspace Alpha-1; Workspace Beta-1
Human owner; human reviewer; worker agent; system service
Active role assignment; expired assignment; revoked delegated grant
Mission revisions 3 and 4; linked requirement and test-plan records
Approval for mission revision 3; artifact/evidence metadata
Run, decision, event, outbox item, and external reference
```

Each test creates only the records it needs from these builders. Fixture IDs,
timestamps, hashes, and clock values must be deterministic. Concurrency tests
use isolated SQLite connections against the same temporary database.

## Required scenario catalogue

| ID | Guarantee | Scenario | Required assertions |
| --- | --- | --- | --- |
| GS-001 | Tenant isolation | An Alpha actor references a Beta workspace/object. | Command denied; no cross-tenant row, event, or outbox item; receipt explains isolation failure. |
| GS-002 | Revision immutability | A finalized mission/approval/evidence record is edited. | Direct mutation fails; correction creates a later revision linked to the prior revision. |
| GS-003 | Approval invalidation | Reviewer approves mission revision 3; revision 4 is created; an actor requests a revision-4 transition. | Revision-3 approval is inapplicable; command denied; no run/transition/success event/outbox; receipt identifies stale approval. |
| GS-004 | Delegated authority | Object grant is active, expired, revoked, or aimed at the wrong revision. | Only the active in-scope grant authorizes; all others fail closed with reason codes. |
| GS-005 | Relationship integrity | Edge has a missing, incompatible, or cross-tenant endpoint. | Database/domain validation rejects it; no dangling graph appears in reconstruction. |
| GS-006 | Lifecycle correctness | Allowed and disallowed task/run transitions are requested under a state-machine version. | Allowed transition records version; invalid transition has no state/event/outbox success effects. |
| GS-007 | Command idempotency | Same command is retried; same key has changed semantic payload. | Exact retry returns original receipt/result; changed payload is rejected; no duplicate state/event/outbox. |
| GS-008 | Evaluation reproducibility | Policy, role, or source changes after an evaluation. | Stored snapshot reproduces original result and cites exact input revisions. |
| GS-009 | Policy precedence | Tenant and workspace configuration conflict; object exception is missing or authorized. | Only declared safe merges apply; unauthorized relaxation fails; authorized exception is scoped and expiring. |
| GS-010 | Atomic success | A permitted command faults at each transactional write boundary. | Either all receipt/evaluation/transition/event/outbox writes commit or none of the success set commits. |
| GS-011 | Auditable rejection | Unauthorized, stale, malformed, and duplicate-conflict commands are submitted. | Appropriate receipt/evaluation persists; target state remains unchanged; no success event/outbox exists. |
| GS-012 | Outbox recovery | Lease holder crashes, recipient receives duplicate delivery, retries exhaust. | Lease recovers; recipient dedup key is stable; attempts append; dead letter and escalation persist; governing decision remains intact. |
| GS-013 | Reconstruction | A representative permitted decision is queried after later revisions exist. | Query reconstructs origin, actor, role/grant, policy, snapshot, edges, events, evidence references, and terminal decision. |
| GS-014 | Legacy migration | Representative current SQLite records are upgraded. | IDs/timestamps survive; provenance is `legacy_import`; no fabricated authority/evidence/decision; legacy behavior remains compatible. |

## Scenario ownership map

The primary owner implements the scenario's governing mechanism. Supporting
tasks contribute dependencies; M1-024 proves the complete integrated scenario
before M1 can exit.

| Scenario | Primary implementation owner | Supporting / final proof |
| --- | --- | --- |
| GS-001 | M1-003 — tenant isolation | M1-014, M1-024 |
| GS-002 | M1-005 — immutable revisions | M1-027–M1-029, M1-024 |
| GS-003 | M1-018 — policy/evaluator applicability | M1-005, M1-012, M1-014, M1-017, M1-024 |
| GS-004 | M1-012 — delegated grants and revocation | M1-011, M1-016, M1-024 |
| GS-005 | M1-009 — typed relationships | M1-007, M1-027–M1-029, M1-024 |
| GS-006 | M1-013 — lifecycle definitions | M1-014, M1-024 |
| GS-007 | M1-015 — command idempotency | M1-014, M1-024 |
| GS-008 | M1-017 — evaluation snapshots | M1-007, M1-024 |
| GS-009 | M1-018 — policy precedence and activation | M1-011, M1-012, M1-016, M1-024 |
| GS-010 | M1-020 — atomic event/outbox creation | M1-014, M1-015, M1-017, M1-019, M1-030, M1-031, M1-024 |
| GS-011 | M1-014 — rejected-command receipts | M1-015, M1-016, M1-017, M1-019, M1-020, M1-024 |
| GS-012 | M1-021 — outbox recovery | M1-024 |
| GS-013 | M1-022 — reconstruction queries | M1-008, M1-009, M1-017, M1-019, M1-021, M1-027–M1-030, M1-024 |
| GS-014 | M1-023 — legacy migration | M1-006, M1-024 |

M1-025 publishes the completed scenario-to-contract trace and must not close
until M1-024 records passing evidence for every scenario.

## Evaluator contract fixtures

Each implemented evaluator needs a versioned fixture set containing allowed,
denied, `require_approval`, and `escalate` outcomes. Fixtures assert the exact
primitive results and reason codes, not only the final boolean.

Initial M1 evaluator coverage should include generic expected-revision,
transition-allowed, actor-permission, grant-scope, and policy-binding behavior.
Full `AcceptMissionEvaluator` semantics remain deferred until M6.

## Definition of done

The specification is ready to constrain implementation when:

- Every locked M1 invariant maps to one or more scenario IDs.
- Every permitted transition has a success scenario and representative rejection
  scenarios.
- Retry, concurrency, transaction, migration, outbox, and reconstruction paths
  are specified.
- Required reason codes, event types, and absence assertions are explicit.
- An implementing agent can add tests without inventing acceptance criteria.

## References

- [M1 design](2026-07-24-m1-durable-governance-kernel-design.md)
- [M1 taskboard](../work-to-be-done/taskboards/m1-governance-kernel/README.md)
- [Shared governance contracts](../work-to-be-done/governance/shared/README.md)
- [Product decision guide](../product-vision/DECISION_GUIDE.md)
