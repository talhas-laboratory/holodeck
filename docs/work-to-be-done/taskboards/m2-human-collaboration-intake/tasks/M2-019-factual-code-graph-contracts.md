# M2-019 — Define factual code-graph contracts and golden fixture

**Status:** ready
**Owner:** unassigned
**Depends on:** M2-016, approved persistent-codebase factual-graph design
**Target baseline:** cumulative M2 review PR #5 at `23a69594878a8f6609d4a3b1d239bf1d10c0de52`

## Objective

Define the provider-neutral domain vocabulary, invariants, deterministic
identity rules, error reasons, and golden Python fixture that every extractor,
store, ingestion service, and query implementation must satisfy.

## Required reading

- `docs/plans/2026-07-29-persistent-codebase-factual-graph-design.md`
- `docs/plans/2026-07-27-workspace-model-and-intelligence-design.md`
- `docs/product-vision/{README,PRODUCT_VISION,DECISION_GUIDE}.md`
- Existing workspace-intelligence domain and tests at the target baseline.

## Scope

- Add pure domain records/enums for graph snapshots, extraction runs, entity
  facts, relation facts, source spans, observation methods, coverage, and
  statuses.
- Lock the initial entity and relation catalogs from the design.
- Define deterministic keys and validation for repository-relative paths,
  spans, endpoint coupling, confidence, revisions, and source observations.
- Add stable domain errors/reasons for malformed facts, unsupported fact kinds,
  revision mismatch, partial coverage, dangling endpoints, and query limits.
- Create a two-revision Python fixture repository plus typed golden facts and
  paths. The fixture must contain one intentionally unresolved dynamic call.
- Define reusable extractor contract assertions without importing a provider.

## Non-goals

- Persistence, extraction, ingestion, graph queries, context compilation, or
  provider packages.
- Generic `entity`/`edge` escape hatches.
- Interpretive claims, component purpose, risk clearance, or task relevance.

## Implementation notes

- Place the domain under
  `holodeck_governance.domain.workspace.intelligence.code_graph`.
- Prefer small modules (`types`, `entities`, `relations`, `snapshots`,
  `extractors`) over one large file.
- Every fact references a registered source and immutable source observation.
- Direct facts have no artificial confidence. `tool_inferred` facts require a
  bounded confidence value and explicit diagnostic/limitation.
- Entity continuity across rename/move is not inferred.
- Absolute paths and mutable branch names are rejected at the domain boundary.

## Acceptance criteria

- Domain records are frozen and validate all invariants without storage imports.
- The entity/relation vocabulary is explicit and versioned.
- Deterministic keys are stable across repeated construction.
- Invalid spans, paths, revisions, relation endpoints, observation methods, and
  confidence combinations fail with stable domain errors.
- Golden facts cover every initial relation kind or explicitly mark a kind
  deferred from the Python fixture.
- The unresolved dynamic call appears as a diagnostic/coverage limitation, not
  a fabricated edge.
- A fresh agent can implement M2-020–M2-022 from these contracts without
  inventing provider or storage semantics.

## Verification

Run:

```bash
uv run pytest -q tests/test_m2_code_graph_contract.py
uv run pytest -q
```

Record exact results, changed files, fixture revision hashes, and residual
risks before moving to done.

## Expected artifacts

- Domain code-graph package.
- `tests/fixtures/code_graph/python_reference/` with deterministic revisions.
- `tests/test_m2_code_graph_contract.py`.
- Contract notes in the task packet if implementation discovers an ambiguity.
