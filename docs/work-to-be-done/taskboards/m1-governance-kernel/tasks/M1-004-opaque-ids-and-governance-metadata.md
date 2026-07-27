# M1-004: Add opaque IDs and shared governance metadata

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-001, M1-002  
Scenarios: supports GS-002 and GS-014


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

## Scope

Implement UUIDv7-style internal IDs and the shared tenant, schema-version,
actor, provenance, and UTC timestamp metadata contract.

## Verification

`python -m pytest -q tests/test_governance_ids_metadata.py` — passed.

## Changed files

- `src/holodeck_governance/domain/ids.py`
- `src/holodeck_governance/domain/metadata.py`
- `tests/test_governance_ids_metadata.py`

## Residual risks

- none known

## Non-goals

- Revision persistence or external-reference storage.
