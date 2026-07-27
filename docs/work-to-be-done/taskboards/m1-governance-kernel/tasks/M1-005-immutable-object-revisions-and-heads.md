# M1-005: Add immutable object revisions and heads

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-003, M1-004  
Scenarios: GS-002, supports GS-003


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

## Scope

Implement stable object IDs, immutable sequential revisions, supersession links,
content hashes, and an explicit current-head lookup.

## Verification

```bash
python -m pytest -q tests/test_governance_revisions.py
```

Results: **4 passed** (immutability, correction/head advance, stale head, concurrent allocation).

## Changed files

- `src/holodeck_governance/domain/registry.py`
- `src/holodeck_governance/domain/revisions.py`
- `src/holodeck_governance/storage/sqlite/migrations.py` (v2)
- `src/holodeck_governance/storage/sqlite/revisions.py`
- `tests/test_governance_revisions.py`

## Residual risks

- Record-family tables still need to bind to registry object_ids (M1-027–029).
- none known for revision mechanics

## Non-goals

- Approval applicability or lifecycle transitions.
