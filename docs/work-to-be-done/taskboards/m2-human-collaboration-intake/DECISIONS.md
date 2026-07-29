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

## 2026-07-29 — M2 release blockers closed

- Accepted origin + outbound/outbox commit atomically; duplicate replay repairs
  missing outbound.
- Genesis propose/decide require `workspace.genesis.propose` /
  `workspace.genesis.decide`.
- MCP pinned to `>=1.6,<2`; CI covers pip and uv installs.
- Binding natural keys use active-only partial unique indexes (migration v18).

## 2026-07-29 — M2-013 workspace intelligence persistence

- Governance migration v19 adds intelligence tables with tenant-coupled
  workspace/actor/reference triggers.
- `WorkspaceIntelligenceApplicationService` / `open_workspace_intelligence_app`
  expose onboard, register/promote sources, modules/items, gaps/contradictions,
  model approve, readiness, and selective stale marking.
- Mutating ops require `workspace.intelligence.curate`.
- Discovery jobs, curator product flow, freshness APIs, and onboarding E2E
  remain M2-014..017; Buzz remains gated.

## 2026-07-29 — M2-014 source discovery and trust classification

- Domain `discovery.py` invents `DiscoveredSourceCandidate` from
  `ObservedSourcePath` via deterministic path/kind heuristics.
- Discovery never invents `instruction_authority`, `authoritative_reference`,
  or `generated_interpretation`.
- `discover_and_register_sources` requires curate permission, registers via
  existing `register_source`, and **skips** natural-key conflicts (idempotent
  rediscovery) rather than failing the batch.
- Explicit observations are the preferred seam (no binding walk required).
- Curator approval/activation, freshness APIs, and onboarding E2E remain
  M2-015..017; Buzz remains gated.

## 2026-07-29 — M2-015 workspace curation, approval, and activation

- Domain `curation.py` defines `WorkspaceCurationProposal` /
  `TrustPromotion` with `validate_curation_proposal` for structural safety.
- Application `validate_curation` / `activate_curation` orchestrate existing
  M2-013 ops; repository `activate_curation` owns one transaction.
- Permission remains `workspace.intelligence.curate`.
- Freshness/query APIs and onboarding E2E remain M2-016..017; Buzz remains
  gated (M2-009).

## 2026-07-29 — M2-015 follow-up: durable promotion authority + open gaps

- **Release blockers found after initial M2-015 done mark** and fixed in this
  follow-up: (1) caller-controlled `authorized_human_promotion: bool` was not
  durable human authority; (2) `open_gap_ids` were not required to equal real
  OPEN gaps.
- Removed the boolean from public `update_source_trust` /
  `validate_curation` / `activate_curation` seams.
- Elevations that need human decision require `decision_id` on
  `TrustPromotion` / `promotion_decision_id` on `update_source_trust`,
  verified against an APPROVED HUMAN `WorkspaceDecision` whose
  `subject_revision_id` is the source (tenant/workspace match).
- Migration v20 adds nullable `gov_workspace_sources.promotion_decision_id`
  referencing `gov_workspace_decisions`; persisted on elevated trust updates.
- `validate_curation` and the activation write txn reject when
  `set(proposal.open_gap_ids) != actual OPEN gap ids`; governed+ with real
  open gaps remains rejected.
- Activating actor still needs `workspace.intelligence.curate`; authorizing
  actor on the decision must be HUMAN (SERVICE activator + HUMAN decision
  may succeed).

## 2026-07-29 — M2-016 refresh, stale propagation, and query snapshot

- Domain `refresh.py` adds `SourceRefreshObservation`,
  `module_ids_depending_on_source`, and `select_preferred_model_revision`.
- Application `propagate_source_stale` / `refresh_sources` require curate;
  `query_workspace_intelligence` is read-only without curate.
- Repository `apply_source_refreshes` updates observed revisions and emits
  existing source/module stale events in one transaction (no new migration).
- Same-revision observations are no-ops; unknown sources raise NotFound.
- Onboarding/refresh E2E remains M2-017; Buzz remains gated (M2-009).

## 2026-07-29 — M2 milestone acceptance blockers (PR-facing)

Release blockers found against M2 acceptance and fixed in this change:

1. **Genesis race / non-human decide** — `decide_workspace_genesis_proposal`
   now begins a write txn first, loads the proposal inside the txn, requires
   HUMAN `decided_by`, then atomically `UPDATE ... WHERE status='proposed'`
   and checks `cursor.rowcount == 1` **before** creating workspace/bindings.
   Concurrent reject-then-approve creates no workspace. Propose also requires
   HUMAN `created_by`. Emits `workspace.genesis.proposed` /
   `workspace.genesis.decided` via `SqliteDomainEventRepository.append` with
   `m2.workspace.genesis.event.v1`.
2. **Caller-trusted readiness** — removed
   `WorkspaceCurationProposal.evidenced_maximum_readiness`. Application
   derives ceilings with `derive_evidenced_maximum_readiness` from durable
   evidence (model/modules/gaps/authority basis + optional HUMAN readiness
   decision). Claims ≥ `GOVERNED` require `readiness_decision_id` to a HUMAN
   APPROVED `WorkspaceDecision` whose subject is the model revision (or
   assessment). Service actors alone cannot claim `operationally_assured` on
   an empty workspace.
3. **Immutable source observations** — migration v21 adds
   `gov_workspace_source_observations` and nullable
   `gov_workspace_sources.current_observation_id`. Register/refresh insert
   observation rows; prior revisions remain queryable via
   `list_source_observations`.
4. **Strict provenance** — `save_context_item` / `save_context_module` (and
   onboard inserts) reject unknown `source_reference_id` / `item_id` /
   `source_id` values with NotFound / Malformed errors.

Board packets added: M2-017 (ready), M2-011 (backlog), M2-009 (blocked),
M2-018 (ready). M2-002/M2-013 done-lane symlinks already present.

## 2026-07-29 — Readiness bypass closed + observation coupling

Follow-up acceptance findings against the prior blocker fix:

1. **Readiness write gate** — all readiness persistence now goes through
   `record_readiness_assessment` (repository + application). It loads durable
   evidence, derives the ceiling with `derive_evidenced_maximum_readiness`,
   rejects claims above that ceiling, and for ≥ `GOVERNED` requires a HUMAN
   APPROVED `WorkspaceDecision` with typed `authorized_readiness_level`.
   `onboard_intelligence`, `save_readiness_assessment`, and `activate_curation`
   share this gate (no unchecked insert paths).
2. **Typed authorized readiness** — migration v22 adds
   `gov_workspace_decisions.authorized_readiness_level`. Curation no longer
   treats `proposal.claimed_readiness_level` as human authorization; it uses
   `decision.authorized_readiness_level` and enforces `claimed <= authorized`.
3. **Observation coupling** — v22 installs tenant/workspace coupling triggers on
   `gov_workspace_source_observations` (must match the referenced source) and
   adds `gov_context_modules.observation_ids_json` / domain
   `ContextModule.observation_ids`. Module save/onboard require observation_ids
   when source_ids are present and validate existence, tenant/workspace, and
   source membership.
4. **Genesis propose relaxed** — non-human actors with propose authority may
   propose; decide remains HUMAN-only.

M2-018 remains **ready** (minimal conversation_context_manifest stub only;
rich Buzz-backed capture workflow not implemented in this change).
