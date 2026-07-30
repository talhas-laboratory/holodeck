# M1-033: Tenant-coupled authority references

Status: done
Owner: implementation-agent  
Gate: done
Depends on: M1-010, M1-011, M1-012, M1-032  
Blocks: M1-024, M1-025  
Scenarios: GS-001, GS-004

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Additive migration **v9** installs authority tenant-coupling triggers without
  modifying prior migrations.
- `gov_revocation_decisions.tenant_id` must match the referenced grant’s tenant.
- `gov_role_assignments.tenant_id` must match `actor_id`’s tenant.
- `gov_delegated_grants.tenant_id` must match both `delegator_actor_id` and
  `recipient_actor_id` tenants.
- Revocation lookup filters by `(tenant_id, grant_id)` (defense in depth).
- Raw-SQL adversarial tests prove Beta cannot insert/update a revocation for an
  Alpha grant; planted Beta revocations cannot deny Alpha authorization; cross-
  tenant assignments/delegations are rejected; same-tenant paths still work.
- Fresh migrate reaches version 9; existing v8 DBs upgrade without losing valid
  same-tenant authority rows.

## Observable acceptance

Beta `gov_revocation_decisions` referencing an Alpha `grant_id` raises
`cross-tenant authority reference forbidden`. Alpha worker authorized by an
Alpha grant remains authorized when a foreign-tenant revocation row is planted
under the pre-v9 schema. Suite green through v9.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_tenant_coupled_authority.py
python -m pytest -q
```

Result: **252 passed** (`python -m pytest -q`, 2026-07-24). Evidence recorded in UPDATES/HANDOFFS run 9.

## Changed files

- `src/holodeck_governance/storage/sqlite/migrate_v9.py`
- `src/holodeck_governance/storage/sqlite/migrations.py`
- `src/holodeck_governance/storage/sqlite/authority.py`
- `tests/test_governance_tenant_coupled_authority.py`

## Residual risks

- Pre-v9 databases may already contain cross-tenant revocation rows; triggers
  stop new ones, and tenant-scoped lookup ignores foreign rows. A one-shot
  cleanup of historical bad rows is out of scope for M1-033.
