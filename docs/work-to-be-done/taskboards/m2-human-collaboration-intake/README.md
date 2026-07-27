# M2 — Human collaboration intake and workspace genesis

Purpose: let an authorized human explicitly initiate governed work through a
replaceable collaboration adapter, producing a durable task origin and an
explainable workspace selection or reversible workspace-genesis proposal.

Board id: `m2-human-collaboration-intake`  
Owner: `talha`  
Status: **ready — M2-005 workspace bindings**

## Boundary

M2 owns collaboration ingress, authenticated actor mapping, durable external
event receipts, task-origin recording, correlated outbound status, and
workspace discovery or creation proposals. It does not compile missions (M3),
define requirement gates (M4), launch agents (M5), or make completion decisions
(M6).

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

## Agent start protocol

1. Read this file, `TASKS.md`, `GATES.md`, `DECISIONS.md`, and recent updates.
2. `M2-001`–`M2-004` are done; implement `M2-005` next for repository/project
   and collaboration-location workspace bindings. Do not build Buzz ingress.
3. Keep provider SDK types inside adapters; domain records use stable external
   references only.
4. Preserve M1 command, tenant, provenance, and outbox guarantees.
5. Do not mark a task done without recorded verification evidence.
