# M3-005 — Rank, filter, and explain context candidates

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-003, M3-004

## Objective

Select the minimum sufficient set of factual evidence, approved knowledge,
task-local hypotheses, and unresolved questions under explicit trust,
freshness, role, and token budgets.

## Scope

- Classify candidates as mandatory, required, useful, optional, or excluded.
- Apply deterministic precedence: platform governance, approved workspace
  instructions, role contract, human task/requirements, run permissions,
  authoritative references, untrusted/generated references, then history.
- Rank using direct task linkage, graph path, source authority, freshness,
  coverage, role applicability, and redundancy.
- Keep binding instructions separate from reference content.
- Record inclusion/exclusion reason, graph path, source revision, trust,
  freshness, estimated size, and truncation.
- Use retrieval handles instead of embedding large sources.

## Acceptance criteria

- Critical binding content cannot be summarized or displaced by lower-trust
  references.
- Stale, conflicted, partial, or untrusted candidates remain labelled.
- Selection is deterministic for identical inputs/configuration.
- Budget exhaustion produces explicit omissions and residual-risk signals.
- More context is not treated as intrinsically better.

## Verification

```bash
uv run pytest -q tests/test_m3_context_selection.py
uv run pytest -q tests/test_m3_context_budgeting.py
uv run pytest -q
```
