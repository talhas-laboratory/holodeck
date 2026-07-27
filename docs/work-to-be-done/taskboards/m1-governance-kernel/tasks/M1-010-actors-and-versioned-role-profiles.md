# M1-010: Add actors and versioned role profiles

Status: done
Owner: implementation-agent  
Gate: done
Depends on: M1-003–M1-005  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: supports GS-004, GS-011

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Actors and versioned role profiles are opaque and tenant-bound.
- Role/actor inserts are immutable (no in-place overwrite).
- RoleProfile.jurisdiction is persisted as jurisdiction_json.

## Observable acceptance

Actors/roles persist immutably; jurisdiction_json round-trips; authority path uses persisted role permissions.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_provenance_authority.py tests/test_governance_p1_enforcement.py -k 'authority or role_profile or jurisdiction'
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Authority INSERT-only immutability + jurisdiction persistence covered in p1 suite; provenance_authority covers actors/roles.

## Changed files

- `src/holodeck_governance/domain/authority/actors.py`
- `src/holodeck_governance/domain/authority/roles.py`
- `src/holodeck_governance/storage/sqlite/authority.py`
- `tests/test_governance_p1_enforcement.py`

## Residual risks

- Role redeployment across tenants is not a product surface in M1.
