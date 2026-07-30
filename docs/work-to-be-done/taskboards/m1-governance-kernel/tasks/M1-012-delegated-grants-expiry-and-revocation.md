# M1-012: Add delegated grants, expiry, and revocation

Status: done
Owner: implementation-agent  
Gate: done
Depends on: see TASKS.md  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: GS-004

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Grants/revocations persist immutably via authority repo.
- Command path surfaces grant expired/revoked/wrong-revision reasons without clobbering to missing-authority.
- GS-004 integrated proof uses persisted fixtures.

## Observable acceptance

Expired grant deny returns DENY_GRANT_EXPIRED on CommandService path; grants cannot be overwritten in place.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_integrated_scenarios.py -k gs004
python -m pytest -q tests/test_governance_p1_enforcement.py -k 'grant or authority'
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: GS-004 requires DENY_GRANT_EXPIRED; for/else clobber removed; immutability covered.

## Changed files

- `src/holodeck_governance/domain/authority/grants.py`
- `src/holodeck_governance/storage/sqlite/authority.py`
- `tests/test_governance_integrated_scenarios.py`
- `tests/test_governance_p1_enforcement.py`

## Residual risks

- Grant redelegation graph not fully exercised beyond single-hop authorize.
