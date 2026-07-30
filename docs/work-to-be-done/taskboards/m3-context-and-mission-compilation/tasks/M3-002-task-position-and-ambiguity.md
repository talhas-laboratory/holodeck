# M3-002 — Persist task position, interpretation, ambiguity, and decisions

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-001

## Objective

Create an inspectable task-position revision that separates what the human said
from what Holodeck inferred, what remains unknown, and which clarifications or
approvals resolved material ambiguity.

## Scope

- Add immutable task-position/interpretation revisions.
- Record desired outcome, scope, non-goals, assumptions, constraints, affected
  concepts, risk hypotheses, authority, confidence, and source provenance.
- Add ambiguity and clarification records with materiality and blocking effect.
- Require authorized decisions for material scope/authority changes.
- Ensure an accepted task position can seed context planning without silently
  becoming requirements or an executable mission.

## Acceptance criteria

- Literal task origin is never overwritten.
- Conflicting interpretations remain visible.
- Material unknowns block or downgrade phase readiness according to policy.
- Revisions are reproducible, tenant-safe, idempotent, and attributable.
- No LLM output directly performs a binding transition.

## Verification

```bash
uv run pytest -q tests/test_m3_task_position.py
uv run pytest -q tests/test_m3_ambiguity_decisions.py
uv run pytest -q
```
