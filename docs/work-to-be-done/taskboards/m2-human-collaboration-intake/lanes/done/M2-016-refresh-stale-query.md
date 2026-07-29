# M2-016 — Implement refresh, stale propagation, and intelligence query APIs

**Status:** done
**Owner:** cursor
**Depends on:** M2-013, M2-014, M2-015

## Outcome

Curators refresh observed source revisions; dependent context modules are
selectively marked stale (WIS-004). A read-only intelligence snapshot query
returns model, sources, modules, open gaps, readiness, and stale id sets
without inventing Buzz ingress or onboarding E2E coverage.

## In scope

- Domain `refresh.py`: `SourceRefreshObservation`,
  `module_ids_depending_on_source`, `select_preferred_model_revision`.
- Application `propagate_source_stale`, `refresh_sources`,
  `query_workspace_intelligence` (+ summary/snapshot dataclasses).
- Repository `apply_source_refreshes` (revision update + selective stale in
  one transaction) and shared stale-event helpers.
- No new migration (reuses v19 intelligence tables).
- Tests for selective stale, unrelated-module freshness, same-revision no-op,
  query snapshot, curate gate, cross-tenant deny, no mission/run.

## Non-goals

- Buzz ingress (M2-009, gated).
- Full onboarding/refresh E2E proof (M2-017).
- New typed command handlers beyond the application seam.
- New SQL migrations.

## Required invariants

- Refresh / propagate require `workspace.intelligence.curate`.
- Query snapshot is read-only and does not require curate.
- Unknown `source_id` / locator raises NotFound.
- Same observed revision is a no-op (no stale events).
- A source change stales only modules listing that source in `source_ids`.
- Cross-tenant / unknown workspace rejected.
- No mission or run objects created.
- Application stays free of sqlite imports.

## Acceptance criteria

- Revision change stales only dependent modules (WIS-004).
- Unrelated modules stay fresh.
- Same-revision refresh is a no-op.
- Query snapshot returns model/sources/modules/gaps/readiness + stale sets.
- Refresh denied without curate; queries continue to work without curate.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_refresh_query.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_workspace_refresh_query.py` → **6 passed**
- `uv run --extra dev pytest -q` → **370 passed in 36.75s**

Changed artifacts:

- `src/holodeck_governance/domain/workspace/intelligence/refresh.py`
- `src/holodeck_governance/domain/workspace/intelligence/__init__.py`
- `src/holodeck_governance/application/workspace_intelligence.py`
- `src/holodeck_governance/storage/sqlite/intelligence.py`
- `tests/test_m2_workspace_refresh_query.py`
- this task packet and the M2 board index/lanes/updates/decisions
- `docs/plans/2026-07-27-workspace-model-and-intelligence-design.md` status line

Next ready task: **M2-017** — prove workspace onboarding and refresh scenarios
(Buzz remains gated at M2-009).

## Residual risks

- Typed intelligence command handlers still deferred to a later seam.
- Onboarding/refresh E2E remains M2-017.
- Buzz ingress remains gated (M2-009).
