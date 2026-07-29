# M3 — Context and mission compilation

Purpose: turn a durable task origin, approved workspace intelligence, and an
exact repository graph snapshot into a bounded, inspectable mission proposal
and the smallest sufficient role-specific context packet.

Board id: `m3-context-and-mission-compilation`
Owner: `talha`
Status: **planned — blocked on M2-011 handoff**

## Boundary

M3 owns typed task intake, task positioning, task-local interpretation,
factual-context planning, relevance selection, immutable context packets,
context expansion, mission proposals, and planning-harness handoff.

M3 does not mutate M2 facts, create requirements/tests/gates (M4), provision
execution workspaces or launch agents (M5), accept work (M6), or treat a coding
harness plan as binding authority.

## Required reading

1. `docs/product-vision/{README,PRODUCT_VISION,DECISION_GUIDE}.md`
2. `docs/plans/2026-07-29-persistent-codebase-factual-graph-design.md`
3. `docs/work-to-be-done/governance/04-curation/specification.md`
4. `docs/work-to-be-done/governance/05-context-compiler/specification.md`
5. M2-011 and `m2-human-collaboration-intake/artifacts/m2-code-graph-m3-handoff.md`

## Agent start protocol

1. Read this board, gates, decisions, recent updates, and the M2 handoff.
2. Complete M3-000 before implementation.
3. Preserve literal human input separately from generated interpretations.
4. Treat M2 graph data as factual evidence with explicit coverage, not as a
   complete model of runtime behavior.
5. Keep all packets immutable, content-hashed, provenance-complete, and
   reproducible.
6. Do not mark a task done without exact verification evidence.
