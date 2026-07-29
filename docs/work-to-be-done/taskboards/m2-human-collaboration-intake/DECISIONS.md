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

## 2026-07-29 — M2 captures bounded source context; M3 interprets it

- An explicit, authorized intake message is the anchor for collaboration
  context. M2 captures the anchor, its direct thread lineage and preceding
  same-thread messages, plus direct attachments and stable explicit references.
- M2 persists that capture as an immutable source manifest with source identity,
  order, relation, trust, retrieval state, and omission reasons. It is evidence
  of available conversation context, not an agent prompt or mission.
- M2 does not infer related channel history, crawl arbitrary linked material,
  semantically rank messages, summarize discussion, or decide what the request
  means. Those interpretation and compilation concerns belong to M3.
- Capture is bounded by policy limits and idempotent on provider/external source
  identity. A provider that cannot retrieve historical context must record the
  missing scope explicitly rather than silently fabricate completeness.

## 2026-07-29 — M2 owns a persistent factual codebase graph

- M2 will persist immutable, revision-scoped code entities and relations for
  each bound repository. SQLite remains the initial canonical store; a graph
  database is not required.
- Holodeck owns the normalized schema, provenance, freshness, activation, and
  bounded query semantics. Extractors are replaceable adapters and their output
  is non-authoritative observation data.
- Persistent facts include directly parsed or statically resolved structure.
  Component purpose, lifecycle, product/security meaning, task relevance, and
  cross-dimensional implications remain M3 task-local hypotheses unless
  separately approved as workspace knowledge.
- Failed or partial extraction never silently replaces a complete active
  snapshot. Missing edges do not establish absence of impact.
- M3 receives bounded factual paths and source evidence, then compiles the
  smallest sufficient context packet. The graph is not dumped into prompts.

## 2026-07-29 — Python AST first; GitNexus is research-only by default

- The first production-compatible extractor uses Python's standard-library AST
  behind a provider-neutral port. This proves the contract without introducing
  a new license or runtime dependency.
- GitNexus is useful as a capability and quality reference, but its current
  PolyForm Noncommercial License 1.0.0 prevents assuming commercial product use.
  It may become an adapter only after an explicit licensing decision.
- Tree-sitter is the preferred later path for broader language coverage. Joern
  may later supply separately labelled deep-analysis observations.
- The provider assessment and factual graph must be benchmarked against cheap
  heuristics and ordinary agent search; architectural elegance is not
  acceptance evidence.
