# M3-006 — Compile immutable role-specific context packets

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-005

## Objective

Compile the exact selected context into immutable, content-hashed,
provenance-complete packets for planners, workers, test agents, reviewers, and
verifiers.

## Scope

- Implement the `ContextPacket` contract from governance section 05.
- Bind workspace model, task position, role, repository snapshot/revision,
  permissions, selected items, required outputs, evidence expectations,
  budgets, omissions, and provenance.
- Produce role-distinct packet views while preserving mandatory truth.
- Store canonical structured content separately from optional provider-specific
  rendering.
- Add deterministic hash/version rules and human-readable preview.
- Prevent untrusted/reference text from escaping into instruction layers.

## Acceptance criteria

- Identical inputs produce identical canonical content and hash.
- Any source/revision/role/budget change creates a new packet.
- Past packets remain reconstructable after workspace or repository refresh.
- Every item is attributable and every omission has a reason.
- Worker, test planner, reviewer, and verifier packets are meaningfully
  different and contract-tested.
- Packets do not contain the whole graph or unrestricted retrieval authority.

## Verification

```bash
uv run pytest -q tests/test_m3_context_packet.py
uv run pytest -q tests/test_m3_context_packet_roles.py
uv run pytest -q tests/test_m3_context_packet_security.py
uv run pytest -q
```
