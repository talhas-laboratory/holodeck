# M2-023 — Ingest, validate, and activate factual graph snapshots

**Status:** ready
**Owner:** unassigned
**Depends on:** M2-021, M2-022

## Objective

Connect repository bindings, workspace sources, the extractor port, and SQLite
persistence through one governed application operation that produces an
atomically active factual graph for an exact revision.

## Scope

- Add governed application commands for graph build/rebuild and status query.
- Resolve tenant-scoped active repository bindings and immutable commits.
- Register or refresh file sources and source observations before facts refer
  to them.
- Normalize extractor candidates into M2-019 facts.
- Persist build/run diagnostics and facts through M2-021.
- Validate revision, source observation, fact vocabulary, spans, endpoints,
  counts, limits, and coverage before activation.
- Atomically activate a successful snapshot and retain the previous active
  snapshot on every failure.
- Emit durable requested, completed, partial, failed, and activated events.
- Provide read-only build/run/snapshot status through the application seam.

## Authority and idempotency

- Mutation requires the existing workspace-intelligence curation authority or
  a narrower graph-refresh permission introduced with an explicit decision.
- The idempotency key binds tenant, workspace, repository binding, revision,
  extractor descriptor, and configuration hash.
- A replay returns the original result. Reusing the key with different inputs
  fails.
- Repository content remains reference data and cannot become instructions.

## Failure scenarios

- Missing/retired binding or unknown revision.
- Checkout changes during extraction.
- Extractor unavailable, timeout, partial output, or malformed output.
- Unknown source observation, invalid span, dangling edge, or cross-tenant ID.
- Transaction crash before and during activation.
- Duplicate and concurrent build requests.

## Acceptance criteria

- A fixture revision creates a complete, queryable active snapshot with exact
  provenance.
- No partial write becomes active.
- Requested and actual revisions are identical.
- Replay is stable and conflicting replay is rejected.
- A failed rebuild leaves the prior active snapshot unchanged.
- Every active fact can be traced to a source observation and extraction run.
- Events and application results use stable schema versions and reason codes.

## Verification

```bash
uv run pytest -q tests/test_m2_code_graph_ingestion.py
uv run pytest -q tests/test_m2_code_graph_failure_recovery.py
uv run pytest -q
```

Record exact commands/results, event evidence, active snapshot IDs, changed
files, and residual risks.

## Expected artifacts

- Application service/command seam.
- Normalization and activation orchestration.
- Ingestion, authority, replay, crash, and concurrent-build tests.
