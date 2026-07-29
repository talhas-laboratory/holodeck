# M2-023 — Ingest, validate, and activate factual graph snapshots

**Status:** done
**Owner:** cursor
**Depends on:** M2-021, M2-022

## Objective

Connect repository bindings, workspace sources, the extractor port, and SQLite
persistence through one governed application operation that produces an
atomically active factual graph for an exact revision.

## Verification

```bash
uv run --extra dev pytest -q tests/test_m2_code_graph_ingestion.py
uv run --extra dev pytest -q tests/test_m2_code_graph_failure_recovery.py
uv run --extra dev pytest -q
```

Results: ingestion+recovery `7 passed`; module contracts green with no
application→sqlite imports.

## Evidence and handoff

- `CodeGraphIngestionService.build_graph`: curate authority → active binding →
  extract → normalize/validate → ensure source observations → persist building
  snapshot/run/facts/memberships → activate (or mark failed).
- Durable events: `build_requested`, `build_completed`/`build_partial`,
  `build_failed`, `snapshot_activated`.
- Idempotency via `gov_command_receipts` fingerprinting tenant/workspace/binding/
  revision/extractor descriptor/limits; replay returns prior result; conflicting
  reuse raises `IdempotencyConflictError`.
- Failed rebuild leaves prior active snapshot unchanged.
- Composition: `open_code_graph_ingestion_app`.

## Residual risks

- Incremental refresh remains M2-024.
- Bounded queries/sentinels remain M2-025.
- Concurrent dual-build races rely on activation `BEGIN IMMEDIATE` contention;
  no separate build-lock table yet.
