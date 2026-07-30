# M2-021 — Persist immutable code-graph snapshots in SQLite

**Status:** done
**Owner:** cursor
**Depends on:** M2-019
**Migration:** `23` (`code_graph_persistence`)

## Objective

Add tenant-safe, immutable SQLite persistence for graph snapshots, extraction
runs, code facts, snapshot memberships, and one active snapshot per repository
binding.

## Verification

```bash
uv run --extra dev pytest -q tests/test_m2_code_graph_migrations.py
uv run --extra dev pytest -q tests/test_m2_code_graph_persistence.py
uv run --extra dev pytest -q
```

Results: migration+persistence tests passed; full suite `444 passed in 41.01s`.

## Evidence and handoff

- `migrate_v23.py`: snapshots, runs, diagnostics, entity/relation facts,
  memberships; partial unique index for one active snapshot per binding;
  tenant/binding/source/observation coupling triggers.
- `SqliteCodeGraphRepository`: building → activate (BEGIN IMMEDIATE, supersede
  prior active), fail without disturbing active, immutable inserts, membership
  reuse across snapshots.
- Tests: additive upgrade from v22, immutability/reuse, failed activation
  preserves prior active, concurrent activation keeps a single active row.

## Residual risks

- Ingestion orchestration remains M2-023.
- Extractor candidate emission remains M2-022.
- Query surface remains M2-025.
