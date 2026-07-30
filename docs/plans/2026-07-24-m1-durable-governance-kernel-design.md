# M1 durable governance kernel design

**Status:** Approved design; implementation in progress (M1 board; milestone not accepted)  
**Milestone:** M1 — Establish the durable governance kernel

## Purpose and boundary

M1 builds Holodeck's constitutional record and decision layer. It makes governed
work attributable, versioned, authorized, auditable, and replayable. It does
not make Holodeck a collaboration platform, agent runtime, context compiler,
test generator, or sandbox.

The kernel is agnostic about agents, models, collaboration platforms,
repositories, and storage adapters. It is deliberately strict about identity,
authority, revisions, state transitions, evidence references, decisions, and
audit history. Adapters translate external requests into kernel commands; they
never write governance state directly.

### Included

- Tenant-aware typed relational records with shared governance metadata.
- Immutable content revisions and append-only operational transitions.
- Actors, versioned roles, workspace assignments, and object-scoped delegated
  grants.
- Provenance, trust classification, external references, and evidence metadata.
- Typed relationships, commands, receipts, policy bindings, evaluations,
  decisions, events, and outbox deliveries.
- Code-defined evaluators with typed governance primitives.
- Initial task/run lifecycle mechanics, migrations, audit queries, and tests.

### Deferred

- Collaboration adapters, external-event inboxes, and signed actor mapping (M2).
- Workspace intelligence, curation, context compilation, and interpretation (M2–M3).
- Requirement/test generation and detailed gate rules (M4).
- Controlled execution environments and agent launchers (M5).
- Evidence sufficiency, independent verification, acceptance, review, and
  learning behavior (M6–M8).

M1 creates typed records and extension seams for later capabilities; it does not
claim their richer behavior already exists.

## Product alignment and current baseline

Holodeck owns governed mission and execution state. Collaboration platforms own
human interaction and signed external events. Repositories and CI own source
revisions, artifacts, and executable verification. M1 preserves this authority
partition by keeping external data in `ExternalReference` records and provider
logic in adapters.

The existing SQLite coordination runtime and the earlier governed-mission thin
slice are migration inputs. Existing records are preserved as imported legacy
data; they are not retroactively described as M1-governed approvals, evidence,
policy evaluations, or decisions.

## Locked decisions

| Area | Decision |
| --- | --- |
| Kernel boundary | Agnostic at adapters; strict about governance in the core. |
| Rule classes | Hard invariants, versioned policy, and intelligent recommendations. Recommendations never have authority. |
| Persistence | Typed relational current state plus append-only audit/event ledger; not full event sourcing. |
| Tenancy | Every governed record belongs to one tenant. Local installs begin with one default tenant. |
| Identity | UUIDv7-style opaque internal IDs. Human labels and external IDs are separate. |
| Revisioning | Stable object ID plus immutable, monotonically increasing revision number. |
| State/content | Material meaning and authority edits create revisions; operational updates create transition records. |
| Relationships | Foreign keys for ownership; typed, versioned edges for cross-cutting traceability. |
| Mutation | Commands are the only mutation path; adapters are thin translators. |
| Evaluators | Explicit code-defined components using typed primitives. Configuration changes parameters, never evaluator logic. |
| Composition | Kernel-defined `all`, `any`, and `at_least`; no generic `not`, arbitrary expression language, query primitive, or stored code. |
| Policy precedence | Hard invariants → tenant policy → workspace policy → authorized object-level exception. Lower levels only tighten unless a safe merge rule exists. |
| Authority | Separate actors and roles; support workspace assignments and object-scoped delegated grants. |
| Grants/approvals | Exact-revision-bound, immutable, attributable, time-bounded, and separately revocable. |
| Evaluation | Evaluate a persisted immutable snapshot. Unknown, missing, or stale inputs fail closed. |
| Atomicity | Command receipt, evaluation, permitted transition, event, and required outbox row commit atomically. |
| Events | UUIDv7 event IDs plus a tenant-local transactional ledger sequence, correlation ID, and causation ID. |
| Outbox | At-least-once recipient-deduplicated delivery with leases, backoff, bounded retry, dead letter, and escalation. |
| Evidence | Store immutable metadata, content hash, and external artifact reference—not artifacts themselves. |
| Lifecycle | Versioned kernel transition definitions, not workspace-editable state machines. |
| Migration | Additive legacy import with explicit provenance and no invented governance semantics. |

## Implementation compatibility decisions

The following decisions are fixed before a builder writes M1 persistence code:

- **Python 3.11 UUID compatibility:** M1 supplies a small, tested internal
  UUIDv7-compatible generator rather than relying on a newer standard-library
  API or adding a runtime dependency. IDs remain opaque; ordering is an
  implementation property, never an authorization input.
- **Typed edge enforcement in SQLite:** every endpoint first has a typed
  `governance_object` registry row. Edge rows reference registry IDs and an
  allowed-edge-type matrix. Foreign keys enforce endpoint existence and tenant
  ownership; a trigger or domain validation, covered by GS-005, enforces the
  endpoint-type matrix. Core relations never live only in JSON.
- **Legacy lifecycle mapping:** the legacy task states `backlog`, `ready`,
  `in-progress`, `review`, `blocked`, `done`, and `cancelled` and legacy run
  states are imported as `legacy_import` facts. They are not silently relabeled
  as M1 transitions. M1-006 defines a documented one-way mapping or explicit
  unsupported status for each value; M1-023 proves it.
- **Transactional ownership:** repositories expose typed persistence contracts;
  application commands open one unit of work. Only that unit of work may commit
  receipt, evaluation, transition, event, outbox, and record-head changes.

## Implementation ownership

The M1 taskboard owns every required concrete record family. M1-027 implements
`Workspace`, `Source`, `Intent`, `Mission`, and `Task`; M1-028 implements
`Requirement`, `TestPlan`, `Run`, `Artifact`, and `Evidence`; M1-029 implements
`Review`, `Approval`, `Decision`, and `Escalation`. M1-030 implements the
repository/unit-of-work seam, and M1-031 publishes the error, reason-code, and
event-schema contracts. No later task may assume these records are present
without declaring the appropriate dependency.

## Rule model

### Hard invariants

Hard invariants are deterministic kernel rules that no policy or override can
disable. They include tenant isolation, immutable finalized records, valid
foreign keys, no dangling typed edges, idempotent command behavior, and
attribution of each decision to an actor and exact subject revision.

### Versioned policy bindings

Policy changes configuration for a known evaluator: required role, approval
count, severity threshold, risk class, effective period, or scope. It cannot
add code, remove an invariant, change evaluator control flow, or reference an
unknown primitive. Activation and replacement require authorized decisions;
older bindings remain available to explain historical evaluations.

### Intelligent recommendations

Agents may propose risk, sources, requirements, or context. These are generated
interpretations with sources, confidence, and model metadata. They cannot cause
a binding transition without command handling and evaluation.

## Domain shape

Every typed record carries a shared envelope:

```text
id, tenant_id, schema_version, created_at, created_by_actor_id,
provenance_ref, status as applicable
```

Mutable conceptual records additionally have a stable `object_id`, immutable
`revision`, `supersedes_revision`, and content hash. Finalized records are
immutable. Timestamps are UTC.

| Family | Typed records | M1 responsibility |
| --- | --- | --- |
| Identity and authority | Tenant, Actor, RoleProfile, RoleAssignment, DelegatedGrant, RevocationDecision | Identity, jurisdiction, delegation, expiry, revocation, and authorization input. |
| Work vocabulary | Workspace, Source, Intent, Mission, Task, Requirement, TestPlan, Run, Artifact, Evidence, Review, Approval, Decision, Escalation | Typed and revisioned vocabulary; later milestones add rich behavior. |
| Provenance | ExternalReference, ProvenanceRecord, TrustClassification, ValidationDecision | Origin, authority class, locator/hash, derivation, and promotion history. |
| Governance control | CommandReceipt, EvaluationSnapshot, EvaluationResult, PolicyBinding, OverrideDecision, TransitionRecord | Commands, policy selection, evaluator result, state changes, and explanation. |
| Audit and delivery | DomainEvent, OutboxItem, OutboxAttempt | Immutable causal ledger and retryable external delivery obligation. |

Ownership uses relational foreign keys. Cross-cutting links use an edge table
with edge type, endpoint object/revision, actor, timestamp, provenance, and
validity status. The database constrains allowed endpoint types per edge type.

## Authority and revision semantics

An actor is a concrete human, agent instance, service, or import process. A role
is a versioned operational contract. Authority is calculated from:

```text
actor + assigned role/grant + jurisdiction + tenant/workspace/object scope
+ exact subject revision + requested command + applicable policy
```

Role assignments and delegated grants are immutable, have effective/expiry
times, and are separately revocable. A delegation identifies delegator,
recipient, permission(s), scope, target revision when object-scoped, policy
basis, expiry, and whether re-delegation is permitted. The default is
non-delegable.

Approvals target exact subject revisions. A later material revision does not
alter past approval records; it makes them inapplicable to the new revision
unless an evaluator expressly permits carry-forward.

## Evaluator contract

Evaluators are code-defined governance components such as
`PrepareTaskEvaluator`, `StartRunEvaluator`, or `AcceptMissionEvaluator`. Their
logic and primitive composition ship with the kernel and are identified by a
contract version and kernel implementation digest.

The evaluator library consists of typed, governance-meaningful primitives:

```text
RevisionMatchesExpected
TransitionIsAllowed
ActorHasPermission
GrantTargetsCurrentRevision
ApprovalFromRoleExists
NoOpenBlockingFindings
EvidenceCoversRequirement
DecisionHasAttribution
```

Primitives have typed inputs and structured outcomes. They cannot run arbitrary
queries, access arbitrary fields, execute stored code, mutate state, or call an
external service. Evaluators are pure: they consume an immutable snapshot and
return `allow`, `deny`, `require_approval`, or `escalate`, with reason codes and
the inspected records.

Each `EvaluationResult` records evaluator contract and implementation versions,
policy binding revisions, subject revisions, actor/role/grant references,
snapshot references, primitive results, final outcome, reason codes, correlation
ID, and timestamp. Rejected commands retain this audit evidence but do not alter
the governed subject's state.

## Command, event, and outbox flow

```text
adapter / CLI / HTTP / future runtime
  -> validated Command
  -> immutable snapshot + evaluator
  -> command receipt and evaluation result
  -> if allowed: transition + domain event + outbox item
  -> one database transaction
```

Commands include opaque ID, type, tenant, actor, role/grant references, target
and expected revision, idempotency key, payload schema version, correlation ID,
and issuance time. Repeating the same semantic command returns the original
receipt. Reusing an idempotency key with different semantics is rejected.

Every event has event ID, tenant-local ledger sequence, type, subject revision
references, actor, timestamp, causation ID, correlation ID, payload schema
version, and immutable payload. Events are audit facts, not delivery jobs.

An outbox item references an event and an adapter-neutral delivery purpose. It
holds a recipient-deduplication key and mutable delivery state. Delivery workers
claim rows through a lease, append attempt records, retry with exponential
backoff, and enter a durable dead-letter state after bounded failure. That state
creates an escalation record; it never reverses the governing decision.

## M1 lifecycle core

```text
Task: draft -> ready -> active -> submitted -> accepted | blocked | cancelled
Run:  created -> active -> completed | failed | interrupted | cancelled
```

Transition definitions are versioned kernel data structures, not workspace
policy configuration. Adding a state later requires a new definition version
and explicit migration behavior. Detailed review, verification, release, and
recovery states are reserved for later milestones.

## Persistence and migration

M1 uses typed relational tables and constraints for tenant ownership, identity,
revisions, current-state lookups, essential foreign keys, unique idempotency
keys, event sequences, edge validity, and active outbox leases. JSON is limited
to bounded versioned payloads and extension metadata, never core governance
relations or authority fields.

Migration is additive:

1. Add a default local tenant and M1 tables without weakening existing
   workspace/task/run/claim guarantees.
2. Import current records with `legacy_import` provenance, preserving source IDs
   and timestamps where available.
3. Link imported records to typed M1 objects without inventing actors, grants,
   approvals, evidence, policy evaluations, or decisions.
4. Retain legacy API behavior behind a thin adapter until parity tests exist.

M1 does not require a graph database or full event sourcing. Current state is
read from relational tables; the append-only ledger supports audit, consistency
checks, and reconstruction verification.

## Verification and exit criteria

The [M1 governance test specification](2026-07-24-m1-governance-test-specification.md) is a required M1 deliverable. It defines executable governance scenarios before persistence and command implementation work begins.

The representative acceptance fixture is manually constructed; it does not
depend on a live agent or collaboration platform:

```text
create tenant and actors
-> assign role / delegate object authority
-> create workspace and source reference
-> create versioned intent, mission, requirement, test, and run records
-> submit a command with an exact expected revision
-> deny unauthorized or stale attempts with durable receipts
-> allow an authorized transition with event and outbox atomically recorded
-> attach immutable evidence metadata and approval for exact revision
-> replay audit links and reconstruct the terminal decision
-> retry the command without duplicate state
-> migrate legacy data and reconstruct the same history
```

M1 is complete only when:

- Tenant isolation, revision immutability, typed relationships, and command
  idempotency are enforced by tests and database constraints where possible.
- A decision is explainable from its command, evaluation snapshot, actor,
  role/grant, policy binding, evidence references, events, and subject revision.
- Rejected, stale, duplicate, and unauthorized commands are safely auditable.
- State/event/outbox atomicity survives injected transaction and worker failure.
- Outbox retries are idempotent and dead-letter escalation is visible.
- Existing data migrates without loss or invented governance claims.
- M2 and M5 adapters can be added without platform or agent SDK types entering
  domain logic.

## References

- [M1 roadmap](../work-to-be-done/BUILD_MILESTONES.md)
- [Shared governance contracts](../work-to-be-done/governance/shared/README.md)
- [Shared governance model](../work-to-be-done/governance/02-shared-governance-model/specification.md)
- [Work graph and gates](../work-to-be-done/governance/06-work-graph-requirements-gates/specification.md)
- [Product vision](../product-vision/PRODUCT_VISION.md)
- [Decision guide](../product-vision/DECISION_GUIDE.md)
- [Buzz integration strategy](../product-vision/BUZZ_INTEGRATION_STRATEGY.md)
