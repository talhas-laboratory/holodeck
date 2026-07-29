# M2-024 — Implement safe incremental graph refresh and invalidation

**Status:** backlog
**Owner:** unassigned
**Depends on:** M2-023

## Objective

Create a new immutable graph snapshot for a changed repository revision while
reusing only facts proven unchanged and propagating source freshness through
existing M2 intelligence.

## Scope

- Accept an exact base snapshot, target revision, and trusted changed-path set
  from a repository adapter or explicit input.
- Refresh changed file sources/observations.
- Compute a conservative re-extraction neighborhood for imports, definitions,
  inheritance, calls, and relation endpoints.
- Reuse old facts only when normalized identity, evidence observation, and
  endpoints are identical.
- Fall back to full extraction when safe incremental coverage cannot be
  established.
- Compare full and incremental output on the two-revision golden fixture.
- Mark dependent context modules stale through the existing M2 refresh seam.
- Retain and reconstruct old snapshots.

## Safety rule

Missing edges never prove that a file or dimension is unaffected. If the
extractor cannot establish incremental completeness, the result is partial or
the system performs a full extraction. A partial refresh does not silently
replace a complete active snapshot.

## Acceptance criteria

- Incremental and full extraction produce equivalent normalized facts for the
  golden target revision.
- Unchanged fact IDs/memberships are reused where the contract permits.
- Changed and removed facts are absent only from the new snapshot.
- The prior snapshot remains exactly queryable.
- Changed source observations stale only dependent context modules.
- Rename, delete, import-target change, and dynamically unresolved cases have
  explicit expected behavior.
- Concurrent refreshes cannot activate an incorrect base/target sequence.

## Verification

```bash
uv run pytest -q tests/test_m2_code_graph_incremental_refresh.py
uv run pytest -q tests/test_m2_workspace_refresh_query.py
uv run pytest -q
```

Record full/incremental equivalence hashes, reused/rebuilt counts, timings,
changed files, and residual unsupported cases.

## Expected artifacts

- Incremental planning/reuse implementation.
- Snapshot comparison support required for verification.
- Refresh, fallback, concurrency, history, and stale-propagation tests.
