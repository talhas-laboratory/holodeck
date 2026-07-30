# M2-013 — Persist workspace intelligence and expose governed application operations

**Status:** done
**Owner:** cursor
**Depends on:** M2-012

## Outcome

Add additive persistence and a governed application seam for workspace
intelligence records defined in M2-012, without discovery jobs, curator UI, or
full onboarding E2E proof.

## In scope

- Migration v19 tables for model revisions, sources, context items/modules,
  gaps, contradictions, decisions, and readiness assessments.
- `SqliteWorkspaceIntelligenceRepository` with tenant coupling, curate
  authority, immutability, and selective stale marking.
- `WorkspaceIntelligenceApplicationService` + `open_workspace_intelligence_app`.
- Atomic `onboard` that persists proposed intelligence and emits M2 events.
- Persistence tests covering WIS-oriented invariants (onboard, trust promotion,
  summary provenance, selective stale, contradictions, readiness bounds,
  authority/tenant denial, natural-key uniqueness).

## Non-goals

- Repository discovery / trust classification jobs (M2-014).
- Curator approval/activation product flow beyond record-level approve (M2-015).
- Freshness query APIs beyond selective stale marking (M2-016).
- Full onboarding/refresh E2E proof (M2-017).
- Buzz ingress (M2-009, gated).
- Typed `workspace.*.` command handlers on `GovernanceApplicationService`
  (bootstrap/admin persistence exception retained).

## Required invariants

- Unknown/disputed/stale content stays explicit.
- Untrusted/generated content cannot become instruction authority without
  authorized human promotion.
- Generated summaries carry confidence and exact source references.
- Source stale marks only listed dependent modules.
- Contradictions remain open until a recorded resolution.
- Readiness governed+ cannot retain open gaps.
- Mutating ops require `workspace.intelligence.curate`.
- Cross-tenant workspace/actor references are rejected.

## Acceptance criteria

- A builder can persist and query intelligence records through the application
  seam.
- Onboarding writes a versioned model, sources, modules/gaps, readiness, and
  durable events without creating missions/runs.
- Trust/readiness/stale/contradiction invariants hold at the persistence
  boundary.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_intelligence_persistence.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_workspace_intelligence_persistence.py` → **9 passed**
- `uv run --extra dev pytest -q` → **351 passed in 36.70s**

Changed artifacts:

- `src/holodeck_governance/storage/sqlite/migrate_v19.py`
- `src/holodeck_governance/storage/sqlite/intelligence.py`
- `src/holodeck_governance/application/workspace_intelligence.py`
- `src/holodeck_governance/composition.py`
- `tests/test_m2_workspace_intelligence_persistence.py`
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-014** — repository/source discovery and trust
classification (Buzz remains gated at M2-009).

## Residual risks

- Typed intelligence command handlers still deferred.
- Discovery/curation/freshness/onboarding E2E remain M2-014..017.
- Buzz ingress remains gated (M2-009).
