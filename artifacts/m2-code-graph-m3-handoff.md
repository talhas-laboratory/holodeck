# M2 → M3 factual code-graph handoff

**Published by:** M2-026  
**For:** independent M3 agents / M3-000  
**Date:** 2026-07-29  
**Acceptance evidence:** `artifacts/m2-code-graph-acceptance-evidence.md`  
**Acceptance metrics:** `artifacts/m2-026-acceptance-metrics.json`

This handoff is sufficient for graph contract details. Final M2→M3 publication
consolidation is **M2-011** (`artifacts/m2-to-m3-handoff.md`) — completed.

---

## 1. Graph schema versions

From `holodeck_governance.domain.workspace.intelligence.code_graph.types`:

| Constant | Value |
| --- | --- |
| `CODE_GRAPH_SCHEMA_VERSION` | `m2.code_graph.v1` |
| `CODE_ENTITY_FACT_SCHEMA_VERSION` | `m2.code_entity_fact.v1` |
| `CODE_RELATION_FACT_SCHEMA_VERSION` | `m2.code_relation_fact.v1` |
| `GRAPH_SNAPSHOT_SCHEMA_VERSION` | `m2.repository_graph_snapshot.v1` |
| `EXTRACTION_RUN_SCHEMA_VERSION` | `m2.repository_extraction_run.v1` |
| `ENTITY_KEY_SCHEMA_VERSION` | `m2.code_entity_key.v1` |
| `RELATION_KEY_SCHEMA_VERSION` | `m2.code_relation_key.v1` |
| `ENTITY_KIND_CATALOG_VERSION` | `m2.code_entity_kind.v1` |
| `RELATION_KIND_CATALOG_VERSION` | `m2.code_relation_kind.v1` |
| Event payload schema | `m2.workspace.code_graph.event.v1` |
| Governance SQLite migration | **v24** (code-graph foundation hardening) |

Closed catalogs: `EntityKind`, `RelationKind`. Unknown kinds are rejected at the
domain boundary — no generic escape hatch.

---

## 2. Active vs historical snapshot rules

- At most **one** `ACTIVE` snapshot per `(tenant, workspace, repository_binding)`.
- Successful rebuild **supersedes** the prior active snapshot; membership rows
  remain queryable by explicit `snapshot_id`.
- `FAILED` / building / partial candidates never become the active replacement
  without a durable policy-decision seam (M2 has none; partial cannot activate).
- Queries default to the active snapshot; pass `GraphQueryScope.snapshot_id` for
  historical reconstruction.
- Empty query results on an active or historical snapshot mean **insufficient
  evidence**, not cleared risk.

---

## 3. Application seams (no SQLite in M3)

### `CodeGraphIngestionService` (mutate; requires `intelligence.curate`)

| Method | Request / result |
| --- | --- |
| `build_graph` | `GraphBuildRequest` → `GraphBuildResult` |
| `get_status` | tenant/workspace/binding → `GraphStatusView` |

`GraphBuildRequest` fields: `tenant_id`, `workspace_object_id`,
`repository_binding_id`, `repository_path`, `requested_revision`, `actor_id`,
`idempotency_key`, `limits` (`ExtractionLimits`), `at`, optional
`base_snapshot_id`, `path_includes`, `path_excludes`, `changed_paths`.

`GraphBuildResult` fields: `snapshot_id`, `extraction_run_id`, `status`,
`coverage_status`, `entity_count`, `relation_count`, `actual_revision`,
`event_types`, `replayed`, `coverage_notes`, `diagnostics`, reuse/rebuild
counts, `incremental`, `fallback_full`.

### `CodeGraphQueryService` (read-only; no curate)

| Method | Scope + args → result |
| --- | --- |
| `get_active_snapshot` | `GraphQueryScope` → `RepositoryGraphSnapshot` |
| `get_snapshot` | `GraphQueryScope` → `RepositoryGraphSnapshot` |
| `find_entities` | path/kind/qn/`QueryBudget` → `FindEntitiesResult` |
| `get_entity` | `entity_fact_id` → `GetEntityResult` |
| `get_neighbors` | id + `TraversalDirection` + budget → `NeighborsResult` |
| `traverse_paths` | id + direction + budget → `TraversePathsResult` |
| `get_change_neighborhood` | changed paths + budget → change neighborhood DTO |
| `get_sources_for_facts` | entity/relation fact ids → `SourcesForFactsResult` |
| `compare_snapshots` | left/right snapshot ids → compare DTO |
| `evaluate_sentinels` | optional changed/ownership/sensitive filters → `SentinelEvaluationResult` |

`GraphQueryScope`: `tenant_id`, `workspace_object_id`, `repository_binding_id`,
optional `snapshot_id`.

M3 must consume these DTOs / domain types. Do **not** import
`SqliteCodeGraphRepository` or extractor adapters from M3 packet compilers.

---

## 4. Bounded query contracts

`QueryBudget(max_depth, max_results, max_visited_nodes [, entity_kinds, relation_kinds])`

- Exhausted budgets return deterministic truncation via `QueryOmissions.reasons`
  (`max_depth`, `max_results`, `max_visited_nodes`).
- `TraversalDirection`: `OUTGOING` | `INCOMING` | `BOTH`.
- Every query result carries `QueryCoverage` (from snapshot coverage) and
  diagnostics summary from the extraction run.
- Neighbor/entity ordering is deterministic by stable keys.

---

## 5. Sentinel contracts

Kinds (`SentinelKind`): `PUBLIC_EXPORT`, `API_ENTRY`, `SCHEMA_OR_MIGRATION`,
`MANIFEST`, `CONFIGURATION`, `TEST_ASSOCIATION`, `OWNERSHIP_TAG`,
`SENSITIVE_PATH_OR_SYMBOL`, `PARTIAL_COVERAGE`.

Statuses: **`ACTIVATED`** or **`UNRESOLVED` only**. Sentinels are **never cleared**.
`No evidence found` ⇒ `UNRESOLVED`, not absence of risk.

---

## 6. Trust / freshness / provenance

- Each entity/relation fact carries `source_id` + `source_observation_id`
  (WorkspaceSource observations).
- `get_sources_for_facts` returns observation/source provenance for fact ids.
- Refresh that writes a new observation on an existing repository-file source
  marks that source stale and propagates STALE only to context modules that
  list that source (M2-016 seam; proven in acceptance).
- Extractor observation methods are data (`direct_parse`, etc.); they do not
  grant instruction authority.

---

## 7. Error / omission / coverage / truncation reasons

`CodeGraphReason` stable codes:

| Code | Meaning |
| --- | --- |
| `code_graph.malformed_fact` | Invalid fact shape |
| `code_graph.unsupported_fact_kind` | Outside closed catalog |
| `code_graph.revision_mismatch` | Requested ≠ actual revision |
| `code_graph.partial_coverage` | Incomplete extract; cannot activate in M2 |
| `code_graph.dangling_endpoint` | Relation endpoint missing |
| `code_graph.query_limit` | Budget/limit contract failure |
| `code_graph.absolute_path` | Non-repository-relative path |
| `code_graph.mutable_revision` | Branch-like / mutable revision rejected |
| `code_graph.invalid_span` | Bad source span |
| `code_graph.invalid_confidence` | Confidence out of range |
| `code_graph.invalid_observation_method` | Unknown observation method |

Coverage: `CoverageStatus` = `complete` | `partial` | `unknown`.  
Diagnostic code for unsupported dynamic calls: `unresolved_dynamic_call`.

---

## 8. Fixture examples

Pinned revisions (`tests/fixtures/code_graph/python_reference`):

| Label | Id |
| --- | --- |
| `rev_a` | `fixture:c059dce6bb6c4dfa257e2cc1d5d737089fea940091e57090d268dc6dae2c21bb` |
| `rev_b` | `fixture:9714592f9bbc4b5c5a7b2548d52d57e88d5af1d43e6e27ac0a9864e0a3ec021e` |

Changed paths `rev_a` → `rev_b`:

- `sample_app/service.py`
- `tests/test_api.py`
- `tests/test_service.py`

Sample query seeds:

- Class: path `sample_app/service.py`, qualified name `Greeter` →
  `sample_app.service.Greeter`
- API: entity kind `api_entry_point` → `sample_app.api.handle_greet`
- Schema: path `sample_app/schema.py`, kind `schema_object`
- Manifest: `pyproject.toml`; config: `config/settings.toml`
- Migration: `migrations/001_init.py`

---

## 9. Non-negotiable rules for M3

1. **Empty results ≠ clear risk.** Treat as unresolved / insufficient evidence.
2. **M3 hypotheses ≠ facts.** Task-local interpretations must remain separate
   records; never write them back as graph facts.
3. **Extractor output is data only.** No prompt, interpretation, or instruction
   authority from providers enters M2 or may be promoted by M3 without a human-
   governed process.
4. **Partial / unsupported coverage reduces readiness honesty** — do not invent
   completeness.

---

## 10. Context-quality benchmark arms (preregistered for M3-000)

Proposed arms from the factual-graph design; **preregistered here for M3-000 to
lock** before any agent-quality run (thresholds must not move after observing
results):

```text
A. ordinary agent search
B. A + typed task intake and cheap sentinels
C. B + bounded factual-graph retrieval
D. C + task-local interpretive probes
```

Primary metrics (proposed; lock in M3-000):

- accepted patch rate;
- consequential affected-component recall;
- regression and high-risk false-negative rate (report high-risk FNs separately);
- required-test and invariant coverage.

Secondary metrics (proposed):

- context precision / recall / F1;
- context actually used in the patch;
- tokens, latency, tool calls;
- extraction and refresh cost;
- stale-fact rate;
- human-review burden.

Promotion logic (proposed): graph justified only if **C beats B** on
cross-component quality without unacceptable cost; interpretive probes proceed
only if **D beats C**. Exact numeric thresholds are **M3-000's lock**, not M2's.

---

## 11. GitNexus

**Research-only.** Current PolyForm Noncommercial 1.0.0 license precludes
assuming commercial redistribution. No GitNexus code, DB, wiki/AGENTS content,
or provider schema may enter Holodeck production dependencies without an
explicit commercial-license decision. See
`artifacts/m2-code-graph-provider-assessment.md`.

---

## 12. Partial / unsupported coverage honesty (readiness)

M2 readiness for graph-backed work must reflect:

- Python stdlib AST is the selected provider; coverage is honest-partial for
  dynamic / multi-language / deep analysis cases.
- Partial snapshots fail closed (no active replacement).
- Unsupported dynamic calls are diagnostics, not edges.
- Incremental refresh requires trusted `changed_paths` or falls back to full.

---

## 13. Related links

- Acceptance evidence: `artifacts/m2-code-graph-acceptance-evidence.md`
- M2-017 onboarding/refresh acceptance:
  `tests/test_m2_017_onboarding_refresh_acceptance.py` (prior board completion)
- Design: `docs/plans/2026-07-29-persistent-codebase-factual-graph-design.md`
- M3-000: `docs/work-to-be-done/taskboards/m3-context-and-mission-compilation/tasks/M3-000-entry-handoff-and-benchmark-protocol.md`
- Final consolidation: M2-011 published `artifacts/m2-to-m3-handoff.md`
