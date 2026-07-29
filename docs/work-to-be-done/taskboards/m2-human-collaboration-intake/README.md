# M2 — Human collaboration intake and workspace genesis

Purpose: let an authorized human explicitly initiate governed work through a
replaceable collaboration adapter, producing a durable task origin and an
explainable workspace selection or reversible workspace-genesis proposal.

Board id: `m2-human-collaboration-intake`
Owner: `talha`
Status: **implementation in cumulative review; M2-024 blocked on foundation hardening; M2-009 Buzz gated**

## Boundary

M2 owns collaboration ingress, authenticated actor mapping, durable external
event receipts, task-origin recording, bounded capture of direct conversation
context into immutable source manifests, correlated outbound status, and
workspace discovery or creation proposals. M2 also owns the revision-scoped
factual representation of bound repositories: observed code entities,
relations, provenance, freshness, and bounded factual queries. It does not
semantically select or summarize task context, create task-local
interpretations, compile missions (M3), define requirement gates (M4), launch
agents (M5), or make completion decisions (M6).

## Required reading

1. `docs/product-vision/README.md`
2. `docs/product-vision/PRODUCT_VISION.md`
3. `docs/product-vision/DECISION_GUIDE.md`
4. `docs/product-vision/BUZZ_INTEGRATION_STRATEGY.md`
5. `../m1-governance-kernel/artifacts/m1-contracts-migration-m2-handoff.md`
6. `../../governance/03-workspace-intelligence/specification.md`
7. `../../governance/04-curation/specification.md`
8. `docs/plans/2026-07-27-m2-collaboration-intake-design.md`
9. `docs/plans/2026-07-27-m2-collaboration-intake-test-specification.md`
10. `docs/plans/2026-07-29-persistent-codebase-factual-graph-design.md`

## Agent start protocol

1. Read this file, `TASKS.md`, `GATES.md`, `DECISIONS.md`, and recent updates.
2. Use cumulative M2 review PR #5 as the implementation baseline until it is
   merged; do not implement new work against the older base branch by accident.
3. `M2-001`–`M2-008`, `M2-010`, `M2-012`–`M2-023` are done. **M2-024** is
   blocked until code-graph foundation hardening lands on the tip. Then
   M2-024–M2-026. **M2-009** (Buzz adapter) remains gated for live ingress.
   `M2-011` waits on `M2-017` (done), `M2-018` (done), and `M2-026`.
4. No collaboration or repository extractor adapter may be built before its
   neutral contract and executable scenario specification are accepted.
5. Keep provider SDK types inside adapters; domain records use stable external
   references only.
6. Preserve M1 command, tenant, provenance, and outbox guarantees.
7. Keep factual graph records separate from M3 interpretations and packets.
8. Do not mark a task done without recorded verification evidence.

## Acceptance-blocker fixes (2026-07-29)

PR-facing note: genesis decide now claims the proposal row first (rowcount==1)
inside a write txn before creating workspaces; decide requires HUMAN actors and
emits `workspace.genesis.proposed` / `workspace.genesis.decided`. Curation
readiness ceilings are **derived** from durable evidence; governed+ claims need
a HUMAN `readiness_decision_id` with typed `authorized_readiness_level`. Source
refreshes append immutable observations (migration v21). Context item/module
provenance IDs are strictly validated. All readiness writes share
`record_readiness_assessment`.
