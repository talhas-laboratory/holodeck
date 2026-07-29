# M3-007 — Compile governed mission proposals and authority boundaries

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-002, M3-006

## Objective

Compile an inspectable mission proposal from the approved task position and
context packet without granting execution authority prematurely.

## Scope

- Define immutable mission proposal/revision records.
- Include desired outcome, scope/non-goals, assumptions, repository revision,
  context packet, roles, permitted/prohibited actions, budgets, stop/cancel
  conditions, escalation, required outputs, evidence expectations, and
  unresolved blockers.
- Derive authority only from durable M1 grants/decisions.
- Require clarification or human approval for material ambiguity, scope
  expansion, high risk, or insufficient authority.
- Separate mission compilation from M4 requirements/gates and M5 execution.

## Acceptance criteria

- A reviewer can trace every mission field to human input, approved workspace
  knowledge, policy, or labelled inference.
- A proposal cannot authorize itself or start a run.
- Repository revision and initial context packet are immutable once a later run
  begins.
- Missing authority and material unresolved hypotheses block readiness.
- Replays are deterministic and tenant-safe.

## Verification

```bash
uv run pytest -q tests/test_m3_mission_proposal.py
uv run pytest -q tests/test_m3_mission_authority.py
uv run pytest -q
```
