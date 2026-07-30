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

- Domain `curation.py`: `TrustPromotion` (with durable `decision_id`),
  `WorkspaceCurationProposal`, `validate_curation_proposal` (structural
  fields, readiness_at_most, governed+ open-gap reject, decision_id shape
  for elevations needing human decision).
- Domain `trust.py`: `trust_promotion_requires_human_decision`,
  `assert_trust_promotion_allowed(decision_id=...)`,
  `assert_trust_promotion_decision_authorizes` (HUMAN + APPROVED +
  subject=source).
- Application `validate_curation` / `activate_curation` requiring
  `workspace.intelligence.curate`; load/verify WorkspaceDecision for each
  elevation that needs a human decision; exact `open_gap_ids` match.
- Repository `activate_curation` owning one transaction; re-checks open
  gaps before readiness insert; persists `promotion_decision_id`.
- Migration v20: nullable `promotion_decision_id` on `gov_workspace_sources`.
- Tests for happy path (HUMAN decision), SERVICE/missing/wrong-subject/
  REJECTED decision denials, SERVICE activator + HUMAN decision success,
  open-gap equality (DISCOVERED + GOVERNED), permission deny, no
  mission/run writes, re-activate already-approved failure.

## Non-goals

- Buzz ingress (M2-009, gated).
- Freshness query APIs (M2-016).
- Full onboarding/refresh E2E proof (M2-017).
- New typed command handlers beyond the application seam.

## Required invariants

- Activation requires `workspace.intelligence.curate`.
- Model must be `proposed`; already-approved reactivation fails cleanly.
- Trust elevations that need human decision require a durable APPROVED
  HUMAN `WorkspaceDecision` whose `subject_revision_id` is the source;
  caller-controlled booleans are not accepted.
- Claimed readiness cannot exceed evidenced maximum; governed+ cannot keep
  open gaps; `open_gap_ids` must exactly equal current OPEN gaps.
- Cross-tenant / unknown IDs rejected.
- No mission or run objects created.
- Application stays free of sqlite imports.

## Acceptance criteria

- A curator can activate a proposed model with module approvals, trust
  promotions, and readiness in one governed transaction.
- Prior approved model revisions are superseded when a new revision activates.
- Silent IA / elevated trust without a valid HUMAN APPROVED decision is
  rejected; SERVICE-authored decisions are rejected.
- SERVICE activator with curate + valid HUMAN decision may succeed.
- `open_gap_ids` inequality rejects even at DISCOVERED; governed+ with
  real open gaps remains rejected.
- Missing curate permission is denied.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_curation.py \
  tests/test_m2_workspace_intelligence_persistence.py \
  tests/test_m2_workspace_intelligence_contract.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Initial verification completed 2026-07-29 (pre-fix):

- `uv run --extra dev pytest -q tests/test_m2_workspace_curation.py` → **6 passed**
- `uv run --extra dev pytest -q` → **364 passed in 35.58s**

**Follow-up authority/readiness fix (this branch):** M2-015 release blockers
found after the initial done mark — caller-controlled
`authorized_human_promotion` boolean was not durable authority, and
`open_gap_ids` were not required to match real OPEN gaps. Fixed by replacing
the boolean with `TrustPromotion.decision_id` / `promotion_decision_id`,
migration v20, HUMAN APPROVED WorkspaceDecision verification, and exact
open-gap equality checks in `validate_curation` and inside the activation
write transaction.

Targeted verification (follow-up):

- `uv run --extra dev pytest -q tests/test_m2_workspace_curation.py tests/test_m2_workspace_intelligence_persistence.py tests/test_m2_workspace_intelligence_contract.py` → **31 passed**
- `uv run --extra dev pytest -q` → **375 passed in 36.39s**

Changed artifacts (follow-up):

- `src/holodeck_governance/domain/workspace/intelligence/trust.py`
- `src/holodeck_governance/domain/workspace/intelligence/curation.py`
- `src/holodeck_governance/domain/workspace/intelligence/sources.py`
- `src/holodeck_governance/domain/workspace/intelligence/__init__.py`
- `src/holodeck_governance/application/workspace_intelligence.py`
- `src/holodeck_governance/storage/sqlite/intelligence.py`
- `src/holodeck_governance/storage/sqlite/migrate_v20.py`
- `src/holodeck_governance/storage/sqlite/migrations.py`
- `tests/test_m2_workspace_curation.py` (+ related contract/persistence)
- this task packet and the M2 board decisions/updates

Next ready task: **M2-016** — refresh, stale propagation, and intelligence
query APIs (Buzz remains gated at M2-009). Status remains **done** only
with the fix evidence above.

## Residual risks

- Typed intelligence command handlers still deferred to a later seam.
- Freshness/query APIs and onboarding E2E remain M2-016..017.
- Buzz ingress remains gated (M2-009).
- Decision signing / external event linkage for WorkspaceDecision remains
  a later collaboration seam (`signed_source_reference_id` optional today).
