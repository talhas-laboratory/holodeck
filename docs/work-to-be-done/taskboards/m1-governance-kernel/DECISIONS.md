# Decisions

## 2026-07-27 — Governed authority-record issuance (M1-034 / migration v10)

- A grant is effective only with an explicit issuance basis. A root basis is an
  active role assignment granting `delegate:<permission>` or `delegate:*`; a
  derived basis is a matching active parent grant marked `redelegatable`.
- A revocation requires the original delegator or an active role assignment
  granting `revoke:<permission>`.
- Existing rows without a basis are preserved but fail closed; M1 must not infer
  historical authority.

## 2026-07-24 — M1 governance kernel

- The kernel is adapter-agnostic and governance-strict.
- Use typed relational current state plus an append-only event/audit ledger.
- Use default-local tenant support now; enforce tenant isolation.
- Use UUIDv7-style opaque IDs, stable object IDs, and immutable sequential revisions.
- Use direct ownership foreign keys plus typed/versioned traceability edges.
- Make commands the sole mutation path and retain every command receipt.
- Use explicit code-defined evaluators and typed governance primitives; policy
  supplies parameters only. No free-form evaluator DSL or generic `not`.
- Bind authority grants and approvals to exact subject revisions; grants are
  expiring and separately revocable.
- Evaluate immutable snapshots and fail closed on incomplete or stale inputs.
- Commit receipt, evaluation, permitted transition, event, and outbox atomically.
- Use at-least-once outbox delivery with leases, backoff, dead letters, and
  escalation.
- Treat existing runtime records as additive `legacy_import` data; never invent
  historic M1 authority or evidence.

## 2026-07-24 — Tenant-coupled authority references (M1-033 / migration v9)

- Gap: revocation lookup selected by `grant_id` alone, and
  `gov_revocation_decisions` FK did not require matching tenant with the grant.
  A Tenant Beta revocation row could revoke a Tenant Alpha grant and deny an
  otherwise-authorized Alpha command. Role assignments and delegated grants
  similarly lacked actor/tenant coupling beyond independent FKs.
- Decision: additive **migration v9** installs BEFORE INSERT/UPDATE triggers
  coupling revocation→grant tenant, assignment→actor tenant, and
  grant→delegator/recipient actor tenants. Do **not** rewrite v5–v8.
- Defense in depth: `actor_may_transition` loads revocations by
  `(tenant_id, grant_id)`.
- M1-033 blocks M1-024/M1-025 review acceptance until structural authority
  isolation is proven by raw-SQL adversarial tests.

## 2026-07-24 — Tenant-coupled object ownership (M1-032 / migration v8)

- Gap: v7 coupled many *relationship* refs to tenant, but omitted a row’s own
  governed identity (`object_id` / `role_object_id`) and several relationship
  columns (mission intent, role assignment role/workspace, evaluation/transition
  subjects, command links, event subjects). That allowed Alpha-owned Source rows
  to reference Beta-owned Source objects under independent SQLite FKs.
- Decision: additive **migration v8** installs reusable BEFORE INSERT/UPDATE
  triggers for own-identity and omitted relationship refs, plus head/revision
  consistency. Do **not** rewrite v7.
- M1-032 blocks M1-024/M1-025 review acceptance until structural tenant isolation
  is proven by raw-SQL adversarial tests.

## 2026-07-24 — Release-blocking enforcement (run 7)

- Approval thresholds require **distinct authorized approvers** for the exact
  subject revision (`approve` permission); cardinality cannot collapse to one row.
- Tenant-coupled references are enforced with SQLite BEFORE INSERT/UPDATE triggers
  that require referenced `gov_objects.tenant_id` to match the row tenant.
- Finalized revisions and append-only ledger/evaluation/receipt/transition tables
  are database-immutable via triggers (migration v7).
- Evaluation persistence stores primitive results, policy binding id, implementation
  id, and selected authority; events store the catalog envelope fields.
- Control-plane adapters depend on `holodeck_governance.composition` /
  `GovernanceApplicationService`, not SQLite command services directly.
- **Command boundary:** M1 production lifecycle mutations are `task.transition` and
  `run.transition` via the application command seam. Bootstrap/admin creates for
  actors, roles, grants, policy bindings, and record families may use storage
  repositories until typed create-command envelopes are added. Seeds and tests
  follow the same rule.

## 2026-07-24 — Executable governance scenarios precede implementation

- M1-002 defines primitive, evaluator-contract, and full governance scenarios
  before persistence and command work begins.
- Downstream implementation packets must trace their test plans to scenario IDs.
- A rejection scenario asserts both the durable audit result and the absence of
  unauthorized state, success event, and success outbox effects.

## 2026-07-24 — Atomic implementation packets

- Replace broad subsystem workstreams with initially 25 dependency-ordered packets.
- Each implementation packet owns one narrow contract or behavior, declares
  scenario IDs, and has one observable verification target.
- M1-024 is the only whole-system proof packet; M1-025 publishes the verified
  contract and M2 handoff.

See the linked design for the complete rationale and acceptance boundary.

## 2026-07-24 — Fresh-builder completeness repair

- The full typed work vocabulary is implemented by explicit record-family packets;
  it is not implicit in revisions, edges, or later scenario fixtures.
- Repository interfaces and the unit-of-work transaction boundary are a dedicated
  M1 deliverable. The boundary owns atomic receipt, evaluation, transition,
  event, and outbox persistence.
- A versioned domain-error/reason-code catalog and event-schema catalog are
  explicit M1 contracts. Tests refer to catalog identifiers, not prose-only
  explanations.
- The existing dirty worktree and governed-mission thin slice are migration
  inputs, not a presumed accepted baseline. `BUILDER_BASELINE.md` defines the
  reproducible starting point and must be refreshed before implementation.
- UUIDv7, legacy lifecycle mapping, and SQLite typed-edge enforcement are
  implementation decisions with named owners and acceptance tests; no builder
  may silently choose incompatible behavior.

## 2026-07-24 — M1 package and migration seams (M1-001)

- New governed code lives in top-level package `holodeck_governance`, sibling to
  legacy `holodeck_control_plane`. Layers: `domain` → `application` →
  `storage` (one-way). Adapters remain in `holodeck_control_plane` and may call
  application services; domain never imports adapters, SQLite, HTTP, MCP, or
  provider SDKs.
- Legacy coordination tables and the governed-mission thin slice stay behind an
  explicit additive migration seam (`holodeck_governance.storage.legacy_seam`
  plus control-plane store adapters). They are not rewritten in place as M1
  authority records.
- Record-family ownership is published in
  `holodeck_governance.domain.vocabulary` and mirrored in
  `artifacts/m1-module-contracts.md`.

## 2026-07-24 — Gap closure decisions

- Cross-tenant command attempts produce durable rejected receipts (GS-001), not
  only raised exceptions.
- CommandService evaluates through typed primitives and persists evaluation
  snapshots/results in the same UoW as receipt/transition/event/outbox.
- M1 governed writes enter via
  `holodeck_control_plane.governance_commands.submit_governance_command`.
  M0 `Store` remains the coordination adapter and must never write `gov_*`.
- GS-001..014 proofs are required for M1-024; component tests do not substitute.

## 2026-07-24 — Residual adapter / graph / migration closure

- HTTP and CLI expose thin translators over `governance_commands`; they do not
  import `CommandService` directly.
- Reconstruction-graph tables are additive migration v4 and are included in
  GS-013 reconstruction when seeded.
- Legacy import covers workspaces/tasks/runs; v4 rollback is version-scoped and
  must leave M0 coordination tables intact.


## 2026-07-24 — Review reopen (enforced kernel)

- M1 is not complete while public callers can supply authorization facts.
- CommandService must resolve tenant ownership, task state/head, role/grant/approval
  applicability from durable records before evaluation.
- Accepted `task.transition` must create a new immutable task revision/head and
  update governed state; transition rows alone are insufficient.
- Material M1 tables (receipts, evaluations, events, transitions, outbox, authority,
  remaining record families) must be numbered-migration owned.
- GS-001 rejection writes a receipt only; it must not append a domain event that
  implies a governed command was processed for the foreign tenant.

## 2026-07-24 — Enforced-kernel rework closeout policy

- Policy bindings in storage are authoritative for `required_approvals`; payload
  `requires_exact_approval` is rejected at the adapter boundary.
- Edge inserts must go through domain endpoint validation before SQLite write.
- Packet re-close after rework: implementation packets may return to `done` with
  GATES evidence; **M1-024/M1-025 stay in `review`** until external acceptance.
- Do not mark the milestone complete while 024/025 remain in review.

## 2026-07-24 — Milestone accepted under enforced-kernel bar

- **Superseded by run 5–7 reopen.** Do not treat this entry as current status.
- Historical note only: an earlier pass marked 024/025 done; subsequent reviews
  found enforcement gaps. Current status is in HANDOFFS.md (milestone not accepted).

## 2026-07-24 — P1 reopen (contention, authority, migrate, run/decision)

- Competing transitions must re-read heads inside `BEGIN IMMEDIATE` and return
  structured stale/contention receipts — never raw UNIQUE crashes.
- Authority facts are append-only; `INSERT OR REPLACE` is forbidden.
- Migration 5 must copy pre-existing lazy command/event/outbox/transition rows
  before dropping old tables.
- Public command surface includes `task.transition` and `run.transition`; accepted
  commands persist a `DecisionRecord` for reconstruction.
- Milestone remains incomplete until reopened packets re-exit GATES with evidence.
