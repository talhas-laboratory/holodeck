# M2-019 — Define factual code-graph contracts and golden fixture

**Status:** done
**Owner:** cursor
**Depends on:** M2-016, approved persistent-codebase factual-graph design
**Target baseline:** cumulative M2 review PR #5 at `e852d65`

## Objective

Define the provider-neutral domain vocabulary, invariants, deterministic
identity keys, error reasons, and golden Python fixture that every extractor,
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

- Domain lives under
  `holodeck_governance.domain.workspace.intelligence.code_graph`
  (`types`, `paths`, `spans`, `entities`, `relations`, `snapshots`,
  `extractors`).
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

```bash
uv run --extra dev pytest -q tests/test_m2_code_graph_contract.py
uv run --extra dev pytest -q
```

Results: `27 passed`; full suite `430 passed in 40.75s`.

Fixture revision hashes (content identity):

- `rev_a`: `fixture:c059dce6bb6c4dfa257e2cc1d5d737089fea940091e57090d268dc6dae2c21bb`
- `rev_b`: `fixture:9714592f9bbc4b5c5a7b2548d52d57e88d5af1d43e6e27ac0a9864e0a3ec021e`
- changed paths: `sample_app/service.py`, `tests/test_api.py`,
  `tests/test_service.py`

## Evidence and handoff

Landed on `cursor/m2-019-factual-code-graph-contracts-2175`:

- Domain package with closed entity/relation catalogs and `CodeGraphReason`
  stable errors.
- Two-revision fixture trees + `revisions.json` + typed golden facts covering
  all initial relation kinds; `Greeter.invoke` dynamic call recorded as
  `unresolved_dynamic_call` diagnostic only.
- `tests/test_m2_code_graph_contract.py` + fixture collect-ignore so realistic
  fixture `test_*.py` files are not collected as Holodeck tests.

## Residual risks

- Extractor port/provider assessment remains M2-020.
- Persistence and ingestion remain M2-021+.
- Fixture `tests/` files are ignored by Holodeck pytest collection via
  `tests/conftest.py` / `norecursedirs`.
