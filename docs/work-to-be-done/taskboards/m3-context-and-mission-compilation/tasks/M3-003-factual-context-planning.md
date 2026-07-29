# M3-003 — Resolve seed entities and build bounded factual context plans

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-002

## Objective

Translate a task position into an explainable, budgeted plan for querying the
M2 factual graph and approved workspace sources.

## Scope

- Resolve task concepts to candidate graph entities using names, aliases,
  paths, source references, sentinels, and approved vocabulary.
- Preserve multiple candidates and unresolved terms.
- Create a deterministic query plan with seed entities, allowed relation/entity
  kinds, directions, depths, budgets, required source classes, and stop rules.
- Execute only through M2 bounded query operations.
- Record every graph path, query, omission, coverage gap, and selection reason.
- Allow targeted iterative deepening without unbounded wandering.

## Acceptance criteria

- Ambiguous entity resolution is visible and never arbitrarily collapsed.
- Query plans are reproducible and enforce budgets.
- Partial M2 coverage propagates into the result.
- Empty graph results remain unresolved.
- A plan cannot query outside tenant/workspace/repository/snapshot scope.

## Verification

```bash
uv run pytest -q tests/test_m3_entity_resolution.py
uv run pytest -q tests/test_m3_factual_context_plan.py
uv run pytest -q
```
