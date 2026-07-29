# M2-022 — Implement the Python reference extractor

**Status:** done
**Owner:** cursor
**Depends on:** M2-019, M2-020

## Objective

Implement the first production-compatible extractor adapter using Python's
standard-library AST and deterministic repository metadata.

## Verification

```bash
uv run --extra dev pytest -q tests/test_m2_python_extractor.py
uv run --extra dev pytest -q tests/test_m2_repository_extractor_contract.py
uv run --extra dev pytest -q
```

Results: extractor+contract tests `15 passed`; metrics in
`artifacts/m2-022-python-extractor-metrics.json` (core kinds at recall 1.0;
CALLS/HANDLES/TESTS/INHERITS/READS/WRITES/EXPOSES/CONFIGURES/MIGRATES precision
1.0; DEFINES/IMPORTS/CONTAINS denser than the curated golden sample).

## Evidence and handoff

- `PythonStdlibAstExtractor` emits normalized candidates through the M2-020
  port: modules/files/classes/functions/methods, imports, inheritance, safe
  CALLS, API HANDLES, TESTS, READS/WRITES, CONFIGURES, MIGRATES, EXPOSES.
- Deterministic UUIDv7-shaped ids; fixture revision = `fixture:<content_hash>`
  checked before and after extraction; limits and excludes produce diagnostics.
- Dynamic `globals()[...]` remains `UNRESOLVED_DYNAMIC_CALL` with no CALLS edge.
- Local/instance type map from constructors, annotations, and `isinstance`
  asserts resolves unambiguous attribute receivers (e.g. `self._store.write_message`,
  `greeter.greet` after isinstance).
- `ExtractionRequest` carries `tenant_id`, `workspace_object_id`, and optional
  `path_source_bindings` for stable fact identity.

## Residual risks

- Ingestion/activation orchestration remains M2-023.
- Incremental refresh remains M2-024.
- Bounded queries/sentinels remain M2-025.
- DEFINES/IMPORTS/CONTAINS are intentionally denser than the curated golden
  sample; compare by recall, not curated precision.
