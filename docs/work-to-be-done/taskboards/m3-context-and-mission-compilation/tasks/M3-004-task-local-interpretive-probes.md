# M3-004 — Implement task-local interpretive probe contracts

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-002, M3-003

## Objective

Allow controlled task-local reasoning over facts without creating a permanent
semantic mirror of the repository.

## Scope

- Define probe activation, inputs, allowed fact/source types, outputs,
  confidence, alternatives, verification obligations, and stop conditions.
- Define `activated`, `cleared`, `unresolved`, and `conflicted`.
- Implement two probes only:
  - data, state, and external contracts;
  - authority, security, and control.
- Require each hypothesis to record premises, factual paths, approved
  workspace claims, inference type, limitations, counter-hypotheses, and
  invalidation conditions.
- Keep outputs task-local and generated/untrusted unless separately promoted.

## Acceptance criteria

- No evidence never yields `cleared`.
- Every `cleared` result contains explicit bounded clearance evidence.
- Model-generated chains are hypotheses, not graph facts.
- Probe failure or insufficient evidence produces unresolved output.
- Probes are optional and cannot mutate M2 or approve mission authority.

## Verification

```bash
uv run pytest -q tests/test_m3_interpretive_probe_contract.py
uv run pytest -q tests/test_m3_initial_probes.py
uv run pytest -q
```
