# M3-008 — Implement context expansion and planning-harness handoff

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-006, M3-007

## Objective

Let an external coding harness receive the exact planning packet, return an
attributable technical plan proposal, and request additional context without
silently mutating the original packet.

## Scope

- Define provider-neutral planning-harness request/result/error contracts.
- Export canonical packets through explicit Codex/Claude-compatible renderers
  or file artifacts without importing provider types into domain code.
- Persist harness/model/version/configuration, timestamps, output hash,
  diagnostics, and source packet.
- Implement structured `ContextExpansionRequest` and governed decision.
- Compile approved expansion into a linked supplemental packet.
- Handle timeout, refusal, malformed output, stale inputs, cancellation, and
  duplicate/replayed requests.

## Authority rule

The harness proposes a plan. It does not modify the mission, approve authority,
create M4 requirements, launch execution, or accept work.

## Acceptance criteria

- A fake harness passes the reusable adapter contract.
- Original packets never change after expansion.
- Expansion respects permissions, trust, freshness, and budgets.
- Denials and omissions are explainable.
- Harness failure leaves durable mission/context state intact.
- The returned plan is generated evidence linked to exact inputs.

## Verification

```bash
uv run pytest -q tests/test_m3_planning_harness_contract.py
uv run pytest -q tests/test_m3_context_expansion.py
uv run pytest -q
```
