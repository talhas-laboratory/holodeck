# Decisions

## 2026-07-27 — M2 boundary and implementation order

- M2 begins with a provider-neutral collaboration contract and executable
  scenario specification; Buzz is the first adapter only after that seam exists.
- An authenticated external event creates a durable, idempotent task origin.
  It does not by itself authorize a mission, run, or acceptance decision.
- Workspace selection is deterministic and explainable. New workspace creation
  remains a reversible proposal until the relevant authorized human decision.
- M2 publishes correlated status through the existing durable-outbox pattern;
  delivery acknowledgement is not proof of downstream processing.

## 2026-07-27 — Guarded M2 start against reviewed M1 handoff

- M1's implementation and M2 handoff artifact are available, but M1-024 and
  M1-025 remain in review pending human milestone acceptance.
- M2 may begin provider-neutral contract, workspace-intelligence, persistence,
  and test-harness work against that reviewed handoff.
- Production Buzz ingress and any external side-effecting provider deployment
  remain deferred until M1 is human-accepted or a later explicit exception
  authorizes them.
- The workspace model is defined by
  `docs/plans/2026-07-27-workspace-model-and-intelligence-design.md`; M2 must
  implement it progressively rather than reducing a workspace to a repository
  locator and name.

## 2026-07-27 — First real collaboration target confirmed

- The user confirmed Buzz as M2's first real collaboration adapter.
- M2-009 remains downstream of the provider-neutral contract and in-memory
  harness; this confirmation does not permit provider-specific domain types or
  production ingress before the guarded-start condition is resolved.

## 2026-07-27 — M2-001 collaboration contract locked

- Provider-neutral intake contracts and CIS-001..008 live under
  `holodeck_governance.domain.collaboration` with design and test
  specifications dated 2026-07-27.
- Stable Holodeck fields are distinct from `adapter_metadata`; receipts dedupe
  on `(tenant_id, provider, external_event_id)`; outbound status uses durable
  outbox idempotency keys correlated to the task origin.
- Intended M1 application-seam command types are
  `collaboration.receipt.record`, `collaboration.origin.record`, and
  `collaboration.outbound.enqueue`. Persistence begins in M2-002.
- Explicit intake grammar is `@holodeck work: <subject>` (with documented
  aliases). Ordinary conversation remains non-executable.

## 2026-07-27 — M2-002 bindings and receipts persisted

- Governance migration v11 adds `gov_collaboration_endpoints`,
  `gov_external_actor_mappings`, and `gov_inbound_event_receipts`.
- `open_collaboration_app` exposes endpoint, actor-mapping, and idempotent
  receipt recording without provider SDK types or task/run mutations.
- Duplicate external events return the prior receipt as `duplicate_replay` and
  do not insert a second row.
- Typed `collaboration.*.record` command handlers remain deferred; this packet
  uses the bootstrap/admin persistence exception.

## 2026-07-27 — M2-003 task origins recorded

- Governance migration v12 adds `gov_task_origins` with source-thread context
  and uniqueness on `(tenant_id, provider, external_event_id)` plus
  `inbound_receipt_id`.
- `CollaborationApplicationService.accept_task_origin` atomically records an
  accepted receipt and linked task origin; replay returns the prior origin.
- Accepted intake still creates no mission, run, approval, or outbox success
  rows; outbound delivery remains M2-004.

## 2026-07-27 — M2 release-blocker fixes

- Collaboration repository writes commit unless a caller owns an explicit
  transaction, so `open_collaboration_app` records are durable across connections.
- `accept_task_origin` requires `verification_result=verified`, an active endpoint,
  an active external-actor mapping, and `collaboration.intake` role authority.
- Migration v13 installs tenant-coupled reference triggers for v11/v12 collaboration
  tables; raw cross-tenant mapping inserts abort.
- Documented verification uses `uv run --extra dev pytest -q` (also available via
  uv default dependency group `dev`).

## 2026-07-27 — Exact accepted-intake mapping attribution

- Accepted receipts and task origins persist `mapping_id`; receipts also persist
  the verified inbound `external_actor_id`.
- `accept_task_origin` requires the exact active mapping for
  endpoint/provider/actor/`external_actor_id`, not merely *some* mapping for the
  claimed Holodeck actor.
- Migration v14 adds the attribution columns and tenant-coupled mapping triggers.

## 2026-07-27 — M2-004 outbound status enqueue

- Governance migration v15 adds `gov_outbound_collaboration_messages`.
- `CollaborationApplicationService.enqueue_outbound_status` validates
  origin/receipt correlation, persists the outbound message, appends
  `governance.outbox.enqueued`, and creates a durable outbox item keyed by the
  semantic idempotency key.
- Adapter `publish_outbound` remains deferred to the harness/Buzz packets.

## 2026-07-29 — M2-005 workspace bindings

- Governance migration v16 adds `gov_repository_bindings` and
  `gov_collaboration_location_bindings` with tenant-coupled triggers.
- Bindings carry explicit `proposed|active|retired` status, provenance
  external references, and creating-actor ownership.
- Intake lookup resolves only **active** bindings by natural key:
  `(tenant, provider, external_repository_id)` or
  `(tenant, endpoint, location_kind, external_location_id)`.
- Channels/repos remain external; they never become the workspace identity.

## 2026-07-29 — M2-006 explainable workspace discovery

- `discover_workspace` ranks active location/repository bindings with stable
  reason codes (`location.exact`, `location.parent`, `repository.exact`,
  agreement/conflict markers).
- Outcomes are explicit: `selected`, `ambiguous`, `unbound`, or
  `ineligible_only`. Suspended/archived workspaces never silently win.
- Discovery is pure evaluation over bindings; genesis remains M2-007.

## 2026-07-29 — M2-007 reversible workspace genesis

- Governance migration v17 adds `gov_workspace_genesis_proposals` with a
  partial unique index for one open (`proposed`) proposal per location
  natural key and tenant-coupled authority/reference triggers.
- `propose_workspace_genesis` requires an unbound discovery outcome and
  records a reversible proposal (no workspace created yet).
- `decide_workspace_genesis` applies approve / reject / withdraw.
  Approve alone registers a Workspace, workspace record, and active
  collaboration-location binding (optional repository binding).
- Reject and withdraw close the proposal without creating workspace state.
- Adapter harness and Buzz decision capture remain M2-008 / M2-009.

## 2026-07-29 — M2-008 in-memory collaboration adapter harness

- `InMemoryCollaborationAdapter` implements `CollaborationAdapter` under
  `holodeck_governance.adapters` (outside domain).
- Provider label is `memory`. Unsigned/invalid signatures and unknown actors
  raise adapter-local `CollaborationAdapterAuthError` (CIS-001 refusal; no
  Holodeck receipt).
- Outbound publish lands in a local mailbox; republish by `idempotency_key`
  returns the prior ack without duplicating the semantic message.
- Domain forbidden-import prefixes now include `holodeck_governance.adapters`.
- Live Buzz ingress (M2-009) remains gated; E2E CIS persistence may proceed
  against this harness as M2-010.

## 2026-07-29 — M2-010 E2E intake against memory harness

- `CollaborationIntakeOrchestrator` normalizes/verifies via `CollaborationAdapter`,
  then records receipts/origins and enqueues correlated outbound status before
  adapter publish.
- `CollaborationAdapterAuthError` lives on the domain adapter port (CIS-001
  refusal without Holodeck receipts).
- E2E coverage proves CIS auth failure, authorization reject, duplicate/replay,
  cross-tenant deny, non-intake ignore, and happy-path correlation without
  mission/run creation.
- Buzz remains gated; next productive track is workspace intelligence (M2-012).

## 2026-07-29 — M2-012 workspace intelligence contracts

- Domain package `holodeck_governance.domain.workspace.intelligence` locks
  model revisions, sources, context items/modules, gaps/contradictions/
  decisions, readiness, trust-promotion rules, and WIS-001..006 expectations.
- Generated/untrusted content cannot become instruction authority without
  authorized human promotion; readiness cannot exceed evidence.
- Persistence and application operations remain M2-013.
