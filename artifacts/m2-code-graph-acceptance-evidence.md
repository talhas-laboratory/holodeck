# M2-026 — Factual code-graph acceptance evidence

**Task:** M2-026  
**Commit:** `15b4849369f3e84ccbb3d19e78db7b06bd0c0dc3`  
**Date:** 2026-07-29  
**Metrics:** `artifacts/m2-026-acceptance-metrics.json`

## Scenario steps (pass/fail)

| Step | Result |
| --- | --- |
| Fresh `migrate_governance` (≥ schema v24) + curate grant + active repository binding | **pass** |
| Build graph for fixture `rev_a` via `CodeGraphIngestionService` + `PythonStdlibAstExtractor` | **pass** (43 entities / 49 relations; ~0.014s) |
| Query entities (module/class/api/test/schema/migration/manifest/config), neighbors, traverse, provenance, sentinels | **pass** |
| Incremental refresh to `rev_b` with `base_snapshot_id` + changed_paths | **pass** |
| Full rebuild of `rev_b` (different idempotency key) ≡ incremental (normalized) | **pass** (45/45 entities, 53/53 relations; zero diffs) |
| Historical `rev_a` queryable via `get_snapshot` + find after supersede | **pass** |
| Changed-source stale: module depending on `sample_app/service.py` becomes STALE; schema-dependent module stays FRESH | **pass** |
| Partial coverage (`max_files=1`) does not activate | **pass** |
| Revision mismatch fails closed (FAILED, no active) | **pass** |
| Idempotent replay returns same snapshot | **pass** |
| Concurrent activation keeps single active | **pass** (`test_m2_026_concurrent_activation_keeps_single_active`) |
| Domain event payloads free of prompt/interpretation authority strings; build/activate types present | **pass** |

## Precision / recall (honest)

Against the golden fixture kinds recorded in
`artifacts/m2-022-python-extractor-metrics.json`:

- Supported behavioral kinds (`calls`, `inherits`, `reads`, `writes`, `exposes`,
  `handles`, `tests`, `configures`, `migrates`) report **precision 1.0 / recall 1.0**.
- Structural kinds (`contains`, `defines`, `imports`) show **high recall (1.0)** but
  **low precision** because the extractor emits more structural edges than the
  minimal golden set. This is expected and must not be read as false negatives
  on supported behavior.
- Dynamic dispatch is recorded as diagnostic `unresolved_dynamic_call` only —
  it never becomes a `CALLS` fact.

## Full vs incremental equivalence

From this acceptance run and `artifacts/m2-024-incremental-refresh-metrics.json`:

| Metric | Full `rev_b` | Incremental `rev_b` |
| --- | --- | --- |
| Entities | 45 | 45 |
| Relations | 53 | 53 |
| Runtime (s) | ~0.014 | ~0.015 |
| Reused entities / relations | — | 13 / 11 |
| Rebuilt entities / relations | — | 32 / 42 |
| Normalized diffs | 0 / 0 / 0 / 0 | same |

## Runtime / fact / reuse counts

See `artifacts/m2-026-acceptance-metrics.json` → `steps.build_rev_a` and
`steps.incremental_vs_full`. Peak memory was not instrumented in this run.

## Migration / fresh install

- Governance schema version after empty `migrate_governance`: **24**.
- Acceptance world always starts from an empty in-memory DB and applies the full
  migration chain (proven in `tests/test_m2_code_graph_acceptance.py::_world`).

## Tenant isolation, auth, idempotency, crash lease, history

- Tenant/workspace/binding scope enforced on query and ingestion paths
  (cross-tenant covered in M2-025; acceptance uses scoped services).
- Mutating builds require `intelligence.curate`; queries are read-only (no curate).
- Idempotent replay returns the same `snapshot_id` with `replayed=True`.
- Build claim leases expire (M2-023 foundation); concurrent activation serializes
  to one active snapshot per binding.
- Superseded snapshots remain membership-queryable.

## Event types emitted

Observed on the lifecycle world:

- `workspace.code_graph.build_requested`
- `workspace.code_graph.build_completed`
- `workspace.code_graph.snapshot_activated`
- `workspace.source.stale` (on source observation refresh during incremental)

Failure worlds additionally emit `workspace.code_graph.build_failed`.

No provider prompt, interpretation, or instruction-authority strings appear in
event payloads.

## Unsupported / dynamic Python cases

- Intentional `globals()`-style dynamic call → `unresolved_dynamic_call` diagnostic.
- Non-Python files are not extracted as Python AST entities (manifest/config/
  schema handled via path heuristics where supported).
- Partial extracts cannot activate without a durable policy-decision seam.

## Explicit M2 authority boundary

M2 stores **facts and diagnostics only**. Extractor output is data. No provider
prompt, interpretation, or instruction authority enters M2 domain events or
active snapshots.

## Residual risks

1. Structural precision vs golden remains low for contains/defines/imports.
2. Impact-neighborhood re-extraction stamps new observations on unchanged bytes.
3. Rename/delete without trusted `changed_paths` requires full fallback.
4. Empty query results never prove absence of risk.
5. Sentinels never emit `cleared`; `unresolved` is the only insufficient-evidence outcome.
6. GitNexus is research-only (PolyForm NC) — not a production dependency.
7. M2-011 still must consolidate this handoff into the final M2→M3 publication.
8. Buzz live ingress (M2-009) remains gated.

## Verification commands and results

```bash
uv run --extra dev pytest -q tests/test_m2_code_graph_acceptance.py
# -> 2 passed

uv run --extra dev pytest -q
# -> 487 passed in 51.46s

uv build
# -> Successfully built dist/holodeck_control_plane-0.1.0.tar.gz
#    Successfully built dist/holodeck_control_plane-0.1.0-py3-none-any.whl

uvx twine check dist/*
# -> Checking dist/holodeck_control_plane-0.1.0-py3-none-any.whl: PASSED
#    Checking dist/holodeck_control_plane-0.1.0.tar.gz: PASSED
# (uvx used because python -m twine was not preinstalled in the env)
```

## Related artifacts

- `artifacts/m2-code-graph-m3-handoff.md`
- `artifacts/m2-017` onboarding evidence (board / prior task)
- `artifacts/m2-022-python-extractor-metrics.json`
- `artifacts/m2-024-incremental-refresh-metrics.json`
- `artifacts/m2-025-code-graph-queries-metrics.json`
- `artifacts/m2-code-graph-provider-assessment.md`
