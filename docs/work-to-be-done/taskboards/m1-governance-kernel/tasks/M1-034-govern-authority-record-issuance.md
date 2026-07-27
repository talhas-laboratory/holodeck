# M1-034: Govern authority-record issuance

Status: done
Owner: implementation-agent  
Gate: done
Depends on: M1-012, M1-033  
Blocks: M1-024, M1-025

## Acceptance criteria

- Grants persist an explicit issuance basis and fail closed without one.
- A role-assignment basis must grant `delegate:<permission>` (or `delegate:*`).
- Parent-grant issuance requires a matching, active `redelegatable` grant.
- Revocation requires either the original delegator or a `revoke:<permission>` role basis.
- Migration v10 preserves rows but never invents a basis for historical authority.

## Verification

```bash
python -m pytest -q tests/test_governance_p1_enforcement.py
python -m pytest -q
```

Result: 12 targeted tests passed; full suite passed after migration v10.

## Changed files

- `src/holodeck_governance/domain/authority/grants.py`
- `src/holodeck_governance/storage/sqlite/authority.py`
- `src/holodeck_governance/storage/sqlite/migrate_v10.py`
- `src/holodeck_governance/storage/sqlite/migrations.py`
- `tests/test_governance_p1_enforcement.py`

## Residual risks

- Historical authority rows without a basis remain queryable but cannot authorize work.
