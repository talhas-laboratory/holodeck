# M2-017 — Prove workspace onboarding and refresh scenarios

**Status:** done
**Owner:** cursor
**Depends on:** M2-012, M2-013, M2-014, M2-015, M2-016

## Outcome

Executable acceptance proof that a workspace can be onboarded with a proposed
model, sources, modules, gaps, and readiness, then curated/activated, then
refreshed with selective stale propagation — without Buzz ingress or mission
compilation.

## In scope

- Scenario script or pytest covering: onboard → discover/register sources →
  curate/activate (with HUMAN trust + readiness decisions where required) →
  refresh observations → query intelligence snapshot.
- Assert immutable source observations retain prior revisions.
- Assert derived readiness ceilings (no caller-trusted evidenced maximum).
- Assert no mission/run objects are created.

## Non-goals

- Buzz adapter (M2-009, gated).
- M2 contracts publication / M3 handoff (M2-011).
- Conversation context preservation (M2-018).

## Required invariants

- Curate permission gates mutating ops.
- HUMAN-only genesis and readiness/trust decisions where required.
- Refresh creates new observation rows; prior observations remain queryable.
- Provenance IDs on context items/modules must resolve in-tenant.

## Acceptance criteria

- End-to-end onboarding + refresh scenario passes under `uv run --extra dev pytest`.
- Snapshot query returns model/sources/modules/gaps/readiness + stale sets.
- Residual risks and M2-009/M2-011 deferrals are explicit.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_017_onboarding_refresh_acceptance.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Acceptance scenario landed on
`cursor/m2-017-onboarding-refresh-acceptance-2175`:

- `tests/test_m2_017_onboarding_refresh_acceptance.py` covers onboard →
  discover/register → reject assured readiness bypass → resolve open gap via
  `resolve_knowledge_gap` → HUMAN trust + readiness decisions → activate
  GOVERNED → refresh observations → query snapshot.
- Asserts discovery never invents instruction authority; refresh appends
  immutable observations while prior revisions remain queryable; snapshot
  returns approved model, sources/modules, empty open gaps, GOVERNED readiness,
  and stale sets; no Mission/Run objects created.

## Residual risks

- Live Buzz ingress remains gated (M2-009).
- Typed intelligence command handlers may still be deferred.
- Factual code-graph lane (M2-019–M2-026) and M2-011 handoff remain open.
