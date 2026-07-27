# M2 collaboration intake design

**Status:** Implementation-ready contract (persistence deferred to M2-002+)  
**Milestone:** M2 — Human collaboration intake and workspace genesis  
**Companion task:** [`M2-001`](../work-to-be-done/taskboards/m2-human-collaboration-intake/tasks/M2-001-collaboration-boundary-and-intake-scenarios.md)  
**Companion test specification:** [`2026-07-27-m2-collaboration-intake-test-specification.md`](2026-07-27-m2-collaboration-intake-test-specification.md)  
**Contract package:** `holodeck_governance.domain.collaboration`

## Purpose

Define the provider-neutral collaboration boundary that every M2 adapter must
satisfy before any Buzz-specific code exists. An authenticated external event
may create a durable, idempotent **task origin**. It must never silently become
a mission, run, approval, or acceptance decision.

This document is the wire-and-authority contract for M2-002 through M2-004.
Persistence, repository discovery, workspace curation, and Buzz ingress remain
out of scope for Run 1.

## Authority partition

| Authority | Owns |
| --- | --- |
| Collaboration provider | Signed conversation events, membership, threads, notifications, external identity proofs. |
| Holodeck | Actor/role mapping used for authorization, inbound receipts, task origins, outbound outbox, workspace selection/genesis proposals. |
| Repository / CI | Revisions, artifacts, executable verification (not M2 intake). |

Adapters translate provider payloads into Holodeck contracts. Domain modules
must never import provider SDKs or protocol schema types.

## Stable Holodeck data versus adapter metadata

### Stable Holodeck fields

These fields are durable domain data. They appear on Holodeck records,
commands, events, and reconstruction:

- opaque IDs (`tenant_id`, `actor_id`, `receipt_id`, `event_id`, `message_id`,
  `task_origin_object_id`, `command_id`, `correlation_id`)
- `provider` string token (`buzz`, `slack`, `github`, `memory`, …) — a label,
  never an SDK type
- `external_event_id`, `external_object_id`, `object_type`, `locator`
- verification outcome (`verified`, `failed`, `unsigned`)
- processing outcome (`accepted_origin`, `rejected`, `ignored_non_intake`,
  `duplicate_replay`)
- intake verb, normalized subject text, policy decision inputs
- conversation location kind and external location identity
- attachment content hash / content type when retained as provenance
- outbound idempotency key and correlation to the task origin / inbound receipt
- M1 `ExternalReference` rows linking Holodeck subjects to external objects

### Adapter metadata

Provider-only fields stay in `adapter_metadata` (or equivalent adapter-local
storage). They must not become domain column types or authorization inputs:

- raw Nostr/Slack/GitHub event JSON or SDK objects
- provider-native enums, kind numbers, relay URLs, npub encodings as typed
  domain fields
- UI display paths, avatars, reaction glyphs, presence state
- transport headers, websocket session IDs, HTTP request IDs
- ephemeral retry counters owned solely by an adapter process

Adapters may round-trip metadata for debugging. Holodeck authorization,
idempotency, and reconstruction must ignore it.

## Contract model

Package: `holodeck_governance.domain.collaboration`.

### VerifiedActorIdentity

Result of verifying a signed external identity and mapping it to a Holodeck
actor.

| Field | Kind | Notes |
| --- | --- | --- |
| `tenant_id` | stable | Opaque Holodeck tenant |
| `actor_id` | stable | Opaque Holodeck actor after mapping |
| `external_identity` | stable | `ExternalReference` for the provider identity |
| `verification_result` | stable | `verified` \| `failed` \| `unsigned` |
| `verified_at` | stable | UTC |
| `adapter_metadata` | adapter | Provider-only verification details |

### ConversationLocation

Provider-neutral collaboration location.

| Field | Kind | Notes |
| --- | --- | --- |
| `location_kind` | stable | `community` \| `channel` \| `thread` \| `dm` \| `project` |
| `external_location` | stable | `ExternalReference` for the location |
| `parent_external_location` | stable | Optional parent (channel→community, thread→channel) |
| `endpoint_id` | stable | Optional Holodeck collaboration-endpoint id once bound |
| `adapter_metadata` | adapter | Display path, icons, provider-native nesting |

### AttachmentRef

| Field | Kind | Notes |
| --- | --- | --- |
| `attachment_id` | stable | Opaque Holodeck id |
| `external_attachment` | stable | `ExternalReference` |
| `content_type` | stable | MIME type when known |
| `content_hash` | stable | Optional content hash |
| `byte_size` | stable | Optional size |
| `adapter_metadata` | adapter | Original filename, CDN URLs, thumbnails |

### NormalizedInboundEvent

Normalized inbound collaboration event after adapter translation.

| Field | Kind | Notes |
| --- | --- | --- |
| `inbound_event_id` | stable | Opaque Holodeck id assigned at normalize |
| `tenant_id` | stable | |
| `provider` | stable | Provider label |
| `external_event_id` | stable | Provider event id; receipt uniqueness partner |
| `occurred_at` / `received_at` | stable | UTC |
| `verified_actor` | stable | `VerifiedActorIdentity` |
| `location` | stable | `ConversationLocation` |
| `body_text` | stable | Literal message body as text |
| `attachments` | stable | Tuple of `AttachmentRef` |
| `source_reference` | stable | `ExternalReference` for the signed source event |
| `adapter_metadata` | adapter | Raw payload excerpts, transport ids |

### InboundEventReceipt / checkpoint

Durable inbound receipt. Uniqueness:

```text
(tenant_id, provider, external_event_id)
```

| Field | Kind | Notes |
| --- | --- | --- |
| `receipt_id` | stable | Opaque |
| `tenant_id`, `provider`, `external_event_id` | stable | Dedupe key |
| `inbound_event_id` | stable | Normalized event |
| `signed_source_reference_id` | stable | `ExternalReference.reference_id` |
| `verification_result` | stable | Copied from actor verification |
| `processing_outcome` | stable | See outcomes below |
| `reason_codes` | stable | Catalog codes |
| `command_id` | stable | Optional M1 command that processed intake |
| `task_origin_object_id` | stable | Set only on `accepted_origin` |
| `checkpoint_token` | stable | Crash/retry resume token |
| `created_at` | stable | UTC |

Processing outcomes:

| Outcome | Meaning |
| --- | --- |
| `accepted_origin` | Explicit authorized intake created a task origin |
| `rejected` | Authenticated/authorized failure or policy deny with receipt |
| `ignored_non_intake` | Ordinary conversation; no origin, no success outbox |
| `duplicate_replay` | Same external event replayed; prior outcome preserved |

A receipt is always written once verification has been attempted for a
deliverable event that Holodeck accepted into its inbox path. Authentication
failures that never produce a tenant-scoped event may omit a tenant receipt;
see CIS-001.

### OutboundCollaborationMessage

| Field | Kind | Notes |
| --- | --- | --- |
| `message_id` | stable | Opaque |
| `tenant_id`, `provider` | stable | |
| `destination` | stable | `ConversationLocation` |
| `body_text` | stable | Status text |
| `task_origin_object_id` | stable | Correlation to origin |
| `inbound_receipt_id` | stable | Correlation to receipt |
| `command_id` | stable | Causation |
| `idempotency_key` | stable | Unique per tenant+provider+semantic intent |
| `created_at` | stable | UTC |

Outbound delivery uses the M1 durable outbox. Delivery acknowledgement is not
proof that a human read the status or that downstream automation finished.

Recommended idempotency key material:

```text
tenant_id + provider + "status" + task_origin_object_id + status_kind
```

### Intake-command grammar

Ordinary conversation is not executable work. Only explicit, supported intake
syntax may request intake.

Canonical grammar (provider-neutral text form):

```text
@holodeck work: <subject>
```

Accepted aliases for the same verb:

```text
@holodeck work <subject>
/holodeck work: <subject>
/holodeck work <subject>
```

Rules:

1. Address token is case-insensitive (`@holodeck`, `@Holodeck`).
2. Verb must be exactly `work` for M2 intake (other verbs deferred).
3. Subject text is required and trimmed; empty subject is malformed intake.
4. Leading/trailing whitespace is insignificant; internal subject whitespace is
   preserved after the first separator.
5. Messages that mention Holodeck without the `work` verb are non-intake.
6. Provider-native mention markup must be normalized to the text form above
   inside the adapter before domain parsing.

`IntakeCommand` fields: `raw_text`, `verb`, `subject_text`, `is_explicit_intake`.

### Intake policy inputs

`IntakePolicyInputs` carries the authorization and automation context evaluated
before an origin is created:

| Field | Purpose |
| --- | --- |
| `tenant_id` | Isolation boundary |
| `actor_id` | Mapped Holodeck actor |
| `location` | Conversation location under evaluation |
| `endpoint_id` | Bound collaboration endpoint, if any |
| `required_capability` | Capability string, e.g. `collaboration.intake` |
| `automation_level` | `manual` \| `assisted` \| `automatic` |
| `allow_unbound_location` | Whether genesis proposal path may start |
| `risk_class` | Initial risk label for later gates (not acceptance) |

Policy evaluation may deny intake. Denial records a `rejected` receipt and must
not create a task origin or success outbox item.

## Mapping to the M1 application seam

All governed mutations enter through:

```text
holodeck_governance.composition.open_governance_app
  -> GovernanceApplicationService.handle(CommandEnvelope) -> CommandReceipt
```

Adapters must not import SQLite command implementations.

### Intended M2 command types (persistence in M2-002+)

| Command type | Purpose | Target |
| --- | --- | --- |
| `collaboration.receipt.record` | Persist inbound receipt / checkpoint | receipt object |
| `collaboration.origin.record` | Create durable task origin + source refs | task-origin object |
| `collaboration.outbound.enqueue` | Enqueue correlated status via outbox | outbound message object |

Until typed create envelopes exist for collaboration records, M2-002 may use the
same bootstrap/admin exception already recorded for M1, but production lifecycle
effects that mutate governed task/run state must still use `handle`.

### Provenance, events, and outbox

Successful `accepted_origin` path (logical write set; tables arrive in M2-002+):

1. `ExternalReference` for the signed source event (and identity/location as
   needed).
2. `InboundEventReceipt` with `processing_outcome=accepted_origin`.
3. Task-origin subject record linked to the source reference and actor.
4. M1 command receipt for the origin command.
5. Domain events: command received/accepted, evaluation completed, transition or
   revision created as applicable, outbox enqueued.
6. Outbox item carrying `OutboundCollaborationMessage` correlation fields.

Rejected / ignored / duplicate paths must not create a new task origin or a new
success status outbox item. Duplicate replay returns the prior receipt outcome.

## CollaborationAdapter port

```text
CollaborationAdapter
  normalize_inbound(raw_provider_payload) -> NormalizedInboundEvent
  verify_and_map_actor(event) -> VerifiedActorIdentity
  publish_outbound(message) -> delivery_ack  # adapter local; Holodeck owns outbox
```

The in-memory harness (M2-008) implements this port. Buzz (M2-009) implements
it later without changing domain types.

## Explicit non-goals (Run 1)

- Buzz SDK, credentials, live ingress, or external side effects
- Persistent M2 tables or migrations
- Repository discovery, workspace curation, workspace intelligence behavior
- Mission compilation, requirement gates, agent launch, acceptance

## Residual risks

- Buzz protocol claims in `BUZZ_INTEGRATION_STRATEGY.md` are dated; revalidate
  before M2-009.
- M1-024/M1-025 remain in human review; only provider-neutral work proceeds.
- Command type names above are contractual for M2 builders; storage shape may
  refine field packing in M2-002 without changing scenario outcomes.
