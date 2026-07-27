# M2 collaboration intake test specification

**Status:** Implementation-ready contract suite (behavioral persistence deferred)  
**Milestone:** M2 — Human collaboration intake and workspace genesis  
**Companion task:** [`M2-001`](../work-to-be-done/taskboards/m2-human-collaboration-intake/tasks/M2-001-collaboration-boundary-and-intake-scenarios.md)  
**Companion design:** [`2026-07-27-m2-collaboration-intake-design.md`](2026-07-27-m2-collaboration-intake-design.md)  
**Scenario catalog:** `holodeck_governance.domain.collaboration.scenario_catalog.CIS_EXPECTATIONS`  
**Contract tests:** `tests/test_m2_collaboration_contract.py`

## Purpose

Lock the executable acceptance scenarios that every M2 collaboration
implementation must satisfy. Component work in M2-002 through M2-004 is
incomplete until these scenario outcomes hold.

Run 1 ships a contract/snapshot suite over the provider-neutral types and the
scenario catalog. Persistence assertions become live as receipts, origins, and
outbox writes land.

## Scenario contract

Every CIS scenario states:

```text
initial state
inbound event / verification inputs
intake parse and policy inputs
command submitted (when any)
expected processing outcome
expected persisted records
expected events
expected outbox actions
expected absent writes
reconstruction / replay expectations
```

For rejection and non-intake paths, tests must prove both:

1. A receipt (or documented auth-failure absence) explains the outcome.
2. No new task origin and no new success outbound status were created.

## Canonical fixture world

Deterministic IDs and clock values from the contract module helpers:

```text
Tenant Alpha; Tenant Beta
Actor Alpha-human; Actor Beta-human
Provider "memory" (in-memory harness label)
Channel Alpha-main; Thread Alpha-main-1
External event E1 (intake); External event E2 (ordinary chat)
```

## Required scenario catalogue

| ID | Guarantee | Primary outcome | Absent writes |
| --- | --- | --- | --- |
| CIS-001 | Authentication | `auth_failed` (no tenant receipt required) | origin, success outbox, governed command accept |
| CIS-002 | Authorization | `rejected` | origin, success outbox |
| CIS-003 | Duplicate delivery | `duplicate_replay` | second origin, second success outbox |
| CIS-004 | Crash / retry | prior outcome preserved after retry | partial duplicate effects |
| CIS-005 | Tenant isolation | `rejected` with cross-tenant deny | cross-tenant origin/outbox |
| CIS-006 | Rejection absence / non-intake | `ignored_non_intake` | origin, success outbox |
| CIS-007 | Source-to-status correlation | `accepted_origin` + correlated outbound | uncorrelated status |
| CIS-008 | Happy-path explicit intake | `accepted_origin` | mission/run/approval/acceptance records |

Exact expected write-set tuples live in `CIS_EXPECTATIONS` and are asserted by
`tests/test_m2_collaboration_contract.py`.

## Scenario narratives

### CIS-001 — Authentication failure

An inbound provider payload cannot be verified (missing/invalid signature).

- Expected: adapter refuses normalization into a trusted tenant event;
  `verification_result=failed` or equivalent auth failure signal.
- Persisted: no Holodeck task origin; no success outbox item; no accepted
  collaboration command.
- Optional: adapter-local dead-letter/log only (not Holodeck governed state).

### CIS-002 — Authorization failure

Event verifies and maps to an actor, intake grammar is valid, but the actor
lacks `collaboration.intake` (or location is forbidden).

- Expected receipt: `processing_outcome=rejected` with missing-authority reason.
- Persisted: inbound receipt + source external reference.
- Absent: task origin; success outbound status; mission/run/approval rows.

### CIS-003 — Duplicate delivery

The same `(tenant_id, provider, external_event_id)` is delivered twice.

- First delivery: `accepted_origin` (or whatever first outcome was).
- Second delivery: `duplicate_replay`; returns the original receipt identity /
  outcome.
- Absent on second delivery: a second task origin; a second success outbox item.

### CIS-004 — Crash / retry

A crash occurs after receipt checkpoint reservation but before commit of the
origin+outbox transaction (or the reverse fault points listed in the catalog).

- Retry with the same external event id resumes via `checkpoint_token`.
- Final state matches a single successful or single rejected outcome.
- Absent: duplicated origins or duplicated success outbox items.

### CIS-005 — Tenant isolation

An Alpha-authenticated actor attempts intake that references Beta tenant
resources (endpoint, workspace binding, or actor mapping).

- Expected: `rejected` with cross-tenant deny.
- Absent: any Beta-tenant origin, event success effect, or outbox item created
  by the Alpha command path.

### CIS-006 — Ordinary conversation / malformed intake

A verified message in an allowed channel does not match intake grammar, or
matches `@holodeck` without `work`, or has an empty subject.

- Expected: `ignored_non_intake` or `rejected` for malformed explicit attempt
  per catalog row.
- Absent: task origin; success outbound status.

### CIS-007 — Source-to-status correlation

Explicit authorized intake succeeds.

- Persisted: receipt (`accepted_origin`), task origin, source external
  reference, outbound message enqueued through durable outbox.
- Outbound message carries `task_origin_object_id`, `inbound_receipt_id`, and
  stable `idempotency_key`.
- Re-delivery of the outbound worker attempt must not create a second semantic
  status (outbox idempotency).

### CIS-008 — Happy-path explicit intake boundary

Same success path as CIS-007 with an explicit assertion that the intake does
**not** create mission, run, approval, or acceptance records. Those remain
later milestones.

## Test layers

| Layer | Run 1 evidence | Later evidence |
| --- | --- | --- |
| Contract types | Construction, invariants, dedupe keys, grammar | unchanged |
| Scenario catalog | Complete CIS-001..008 write-set declarations | unchanged |
| Boundary | Domain collaboration package imports no provider SDK | unchanged |
| Persistence scenarios | Deferred | M2-002..M2-004 / M2-010 |

## Verification commands

```text
uv run pytest -q tests/test_m2_collaboration_contract.py
uv run pytest -q
```
