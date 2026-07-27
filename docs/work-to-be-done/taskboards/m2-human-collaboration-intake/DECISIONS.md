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
