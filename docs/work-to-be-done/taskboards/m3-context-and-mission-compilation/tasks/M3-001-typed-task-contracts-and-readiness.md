# M3-001 — Define typed task contracts and phase readiness

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-000

## Objective

Convert a literal task origin into a typed, provenance-preserving intake
contract that determines whether Holodeck may investigate, compile an
implementation mission, or must stop for clarification.

## Scope

- Define task types initially covering bug fix, feature, refactor, performance,
  security, investigation, and documentation.
- Define common fields: literal request, observed/desired outcome, actors,
  environment, reproduction/evidence, scope, non-goals, constraints, acceptance
  signals, unknowns, and source references.
- Define per-type required/optional evidence and readiness rules.
- Define `READY`, `DISCOVERY_READY`, and `BLOCKED`.
- Extract only explicitly available fields automatically; inferred values remain
  separate candidates.
- Provide schema-versioned human-readable YAML serialization while canonical
  state remains typed persistence.

## Acceptance criteria

- Empty or ambiguous fields remain unresolved.
- The same origin and source manifest produce deterministic intake state.
- Investigation can proceed with less information than implementation.
- Security/high-impact tasks require stronger evidence/authority.
- User-provided, repository-observed, agent-inferred, and approved values remain
  distinguishable.

## Verification

```bash
uv run pytest -q tests/test_m3_task_contracts.py
uv run pytest -q
```
