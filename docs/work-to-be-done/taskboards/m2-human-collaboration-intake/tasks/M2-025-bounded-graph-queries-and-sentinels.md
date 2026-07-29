# M2-025 — Expose bounded factual queries and high-recall sentinels

**Status:** backlog
**Owner:** unassigned
**Depends on:** M2-023, M2-024

## Objective

Expose a safe, explainable factual query surface for M3 and deterministic
warnings that provide the cheap baseline for later quality experiments.

## Scope

- Implement active/historical snapshot retrieval.
- Implement entity lookup/search by path, kind, language, and qualified name.
- Implement neighbor, bounded path, change-neighborhood, source-provenance, and
  snapshot-comparison queries.
- Require explicit direction, relation/entity allowlists, maximum depth,
  maximum results, and maximum visited nodes.
- Return graph paths, source observations, coverage, truncation, omissions, and
  diagnostics with every result.
- Implement sentinels for public exports/APIs, schemas/migrations, manifests,
  configuration, tests, ownership tags, sensitive paths/symbols, and partial
  graph coverage.
- Add application operations; HTTP/CLI adapters are optional only if the
  current project pattern requires them for acceptance.

## Query rules

- No arbitrary SQL, Cypher, provider-native query, or unbounded traversal.
- Tenant, workspace, repository binding, and snapshot are mandatory.
- Default queries use the active snapshot; historical queries require an
  explicit snapshot ID.
- Empty results do not assert absence of dependency or risk.
- Sentinels activate attention but never produce a `cleared` decision.

## Acceptance criteria

- Golden queries return expected entities, paths, and exact evidence.
- Traversal order and truncation are deterministic.
- Cross-tenant and cross-workspace access fails.
- Query limits prevent graph explosion and expose why results were omitted.
- Change sentinels have golden expected outputs for both fixture revisions.
- Partial coverage is visible in every relevant result.
- M3 can consume results without importing SQLite or extractor code.

## Verification

```bash
uv run pytest -q tests/test_m2_code_graph_queries.py
uv run pytest -q tests/test_m2_code_graph_sentinels.py
uv run pytest -q
```

Record query-plan/index evidence, deterministic output hashes, limit behavior,
changed files, and residual risks.

## Expected artifacts

- Query request/result domain contracts.
- Repository/application query operations.
- Sentinel catalog and results.
- Query, budget, tenant, history, provenance, and sentinel tests.
