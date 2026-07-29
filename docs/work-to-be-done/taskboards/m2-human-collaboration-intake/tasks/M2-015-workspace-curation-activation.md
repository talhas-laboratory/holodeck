# M2-015 — Implement workspace curation, approval, activation, and readiness

**Status:** done
**Owner:** cursor
**Depends on:** M2-012, M2-013, M2-014

## Outcome

Curators submit a structured `WorkspaceCurationProposal`; deterministic
validation and a single-transaction activation approve the model revision,
listed context modules, explicit trust promotions, and a readiness
assessment without inventing Buzz ingress or freshness query APIs.

## In scope

- Domain `curation.py`: `TrustPromotion`, `WorkspaceCurationProposal`,
  `validate_curation_proposal` (structural fields, readiness_at_most,
  governed+ open-gap reject, silent IA promotion reject).
- Application `validate_curation` / `activate_curation` requiring
  `workspace.intelligence.curate` only.
- Repository `activate_curation` owning one transaction over existing
  trust/approve/readiness insert + event append helpers.
- No new migration (reuses v19 intelligence tables).
- Tests for happy path, silent IA deny, validation rejects, permission
  deny, no mission/run writes, and re-activate already-approved failure.

## Non-goals

- Buzz ingress (M2-009, gated).
- Freshness query APIs (M2-016).
- Full onboarding/refresh E2E proof (M2-017).
- New typed command handlers beyond the application seam.
- New SQL migrations.

## Required invariants

- Activation requires `workspace.intelligence.curate`.
- Model must be `proposed`; already-approved reactivation fails cleanly.
- Trust promotions never silently escalate to instruction authority.
- Claimed readiness cannot exceed evidenced maximum; governed+ cannot keep
  open gaps.
- Cross-tenant / unknown IDs rejected.
- No mission or run objects created.
- Application stays free of sqlite imports.

## Acceptance criteria

- A curator can activate a proposed model with module approvals, trust
  promotions, and readiness in one governed transaction.
- Prior approved model revisions are superseded when a new revision activates.
- Silent IA promotion without `authorized_human_promotion` is rejected.
- Missing curate permission is denied.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_curation.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_workspace_curation.py` → **6 passed**
- `uv run --extra dev pytest -q` → **364 passed in 35.58s**

Changed artifacts:

- `src/holodeck_governance/domain/workspace/intelligence/curation.py`
- `src/holodeck_governance/domain/workspace/intelligence/__init__.py`
- `src/holodeck_governance/application/workspace_intelligence.py`
- `src/holodeck_governance/storage/sqlite/intelligence.py`
- `tests/test_m2_workspace_curation.py`
- this task packet and the M2 board index/lanes/updates/decisions
- `docs/plans/2026-07-27-workspace-model-and-intelligence-design.md` status line

Next ready task: **M2-016** — refresh, stale propagation, and intelligence
query APIs (Buzz remains gated at M2-009).

## Residual risks

- Typed intelligence command handlers still deferred to a later seam.
- Freshness/query APIs and onboarding E2E remain M2-016..017.
- Buzz ingress remains gated (M2-009).
