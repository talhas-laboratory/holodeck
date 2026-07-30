# M2-012 — Define workspace intelligence records and contracts

**Status:** done
**Owner:** cursor
**Depends on:** M2-000

## Outcome

Lock provider-neutral workspace-intelligence contracts — model revisions,
sources, context items/modules, gaps/contradictions/decisions, readiness, trust
promotion rules, and WIS-001..006 scenario expectations — before persistence.

## In scope

- Domain package `holodeck_governance.domain.workspace.intelligence`.
- Required seven-section model revision + intent seed.
- Source trust classes with no silent instruction-authority promotion.
- Context items/modules with generated-summary provenance rules.
- Knowledge gaps, contradictions, workspace decisions.
- Readiness levels bounded by evidence; governed+ forbids open gaps.
- Contractual command/event names and WIS scenario catalogue.
- Contract tests and design-doc status update.

## Non-goals

- Additive persistence or application operations (M2-013).
- Repository discovery / trust classification jobs (M2-014).
- Curator approval/activation flow (M2-015).
- Freshness propagation APIs (M2-016).
- Onboarding E2E proof (M2-017).
- Buzz ingress (M2-009, gated).

## Required invariants

- Unknown/disputed/stale content stays explicit; never invent certainty.
- Generated interpretations cannot become instruction authority by themselves.
- Untrusted/generated promotion to instruction authority requires authorized
  human promotion.
- Readiness cannot exceed available evidence/approved authority.
- Domain package imports no application, storage, adapters, or provider SDKs.

## Acceptance criteria

- A builder can implement M2-013 without inventing intelligence wire contracts.
- WIS-001..006 catalogue declares expected records/events/absent writes.
- Contract suite proves model completeness, trust rules, summary provenance,
  contradiction openness, and readiness bounds.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_intelligence_contract.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_workspace_intelligence_contract.py` → **11 passed**
- `uv run --extra dev pytest -q` → **335 passed in 32.45s**

Changed artifacts:

- `src/holodeck_governance/domain/workspace/intelligence/`
- `docs/plans/2026-07-27-workspace-model-and-intelligence-design.md`
- `tests/test_m2_workspace_intelligence_contract.py`
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-013** — Persist workspace intelligence and expose
governed application operations.

## Residual risks

- Persistence packing may refine in M2-013 without changing WIS outcomes.
- Buzz remains gated (M2-009).
- Onboarding proof remains M2-017.
