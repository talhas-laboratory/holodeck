# M2-021 — Persist immutable code-graph snapshots in SQLite

**Status:** ready
**Owner:** unassigned
**Depends on:** M2-019

## Objective

Add tenant-safe, immutable SQLite persistence for graph snapshots, extraction
runs, code facts, snapshot memberships, and one active snapshot per repository
binding.

## Scope

- Add an additive migration after the current cumulative M2 schema version.
- Add tables for snapshots, extraction runs, entity facts, relation facts,
  snapshot memberships, diagnostics, and active-snapshot selection.
- Add foreign keys and triggers coupling tenant, workspace, repository binding,
  source, observation, fact endpoints, run, and snapshot.
- Add repository protocols and SQLite implementations.
- Add indexes for entity lookup, relation expansion, source lookup, snapshot
  comparison, and active-snapshot resolution.
- Preserve content-addressed reuse of unchanged facts through memberships.
- Provide transaction helpers for building, failing, validating, and atomically
  activating snapshots.

## Invariants

- At most one active snapshot exists per tenant/workspace/repository binding.
- Building or failed snapshots are never returned as active.
- Facts and memberships are immutable after insertion.
- Relations cannot cross tenant, workspace, repository binding, or snapshot
  membership.
- Every fact references an existing registered source observation.
- Activation succeeds only when requested and actual revisions match and all
  endpoints are present.
- Replaying the same command is idempotent; conflicting payloads fail.
- Historical active/superseded snapshots remain queryable.

## Non-goals

- Graph database, Cypher, provider-native persistence, extraction, or M3 query
  planning.
- Copying repository contents into the graph tables.

## Acceptance criteria

- Migration upgrade works from a database at the cumulative M2 baseline.
- Tenant/workspace/repository/source-observation mismatches are rejected by
  storage constraints, not just application checks.
- Concurrent activation attempts cannot produce two active snapshots.
- Failed activation preserves the previous active snapshot.
- Identical facts may be shared by snapshot memberships; changed facts remain
  historically distinct.
- Query plans use the intended indexes for bounded fixture traversals.

## Verification

```bash
uv run pytest -q tests/test_m2_code_graph_migrations.py
uv run pytest -q tests/test_m2_code_graph_persistence.py
uv run pytest -q
```

Record the migration number, schema dump/checks, concurrency result, changed
files, and residual risks.

## Expected artifacts

- Additive SQLite migration.
- Storage port and SQLite repository.
- Migration, coupling, immutability, replay, and concurrency tests.
