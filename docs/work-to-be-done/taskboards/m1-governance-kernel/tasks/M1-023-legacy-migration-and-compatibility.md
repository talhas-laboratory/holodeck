# M1-023: Execute legacy migration and compatibility tests

Status: done
Owner: implementation-agent  
Gate: done
Depends on: M1-006, M1-013–M1-022  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Representative M0 upgrade preserves IDs/status with legacy_import provenance.
- migrate_v5 preserves pre-v5 command/outbox rows; edge copy fails closed.
- migrate_v6 refuses to wipe non-empty unmappable evidence.

## Observable acceptance

GS-014 + p1 migrate_v5 edge fail-closed + pre-v5 copy fixtures.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_reconstruction_migration.py tests/test_governance_p1_enforcement.py -k migrate
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Legacy import + migrate fail-closed proofs after P0/P1.

## Changed files

- `src/holodeck_governance/storage/sqlite/legacy_import.py`
- `src/holodeck_governance/storage/sqlite/migrate_v5.py`
- `src/holodeck_governance/storage/sqlite/migrate_v6.py`
- `tests/test_governance_p1_enforcement.py`

## Residual risks

- Rollback version-scoped for v4–v6; not every historical M0 table family is imported.
