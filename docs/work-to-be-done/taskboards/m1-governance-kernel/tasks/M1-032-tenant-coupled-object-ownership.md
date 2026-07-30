# M1-032: Enforce tenant-coupled object ownership

Status: done
Owner: implementation-agent  
Gate: done
Depends on: M1-003, M1-005, M1-023  
Blocks: M1-024, M1-025  
Scenarios: GS-001 (structural tenant isolation)

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Additive migration **v8** installs tenant/object ownership triggers without modifying v7.
- Every row that declares `tenant_id` and references a governed object proves that
  object belongs to the same tenant (own identity + relationship refs).
- `gov_object_heads` revision consistency requires matching tenant, object_id, and
  revision number.
- Raw-SQL adversarial tests prove same-tenant success and cross-tenant insert/update
  rejection with unchanged original rows.
- Fresh migrate reaches version 8; existing v7 DBs upgrade without losing valid rows.

## Observable acceptance

Alpha `gov_sources.tenant_id` + Beta `object_id` raises
`cross-tenant reference forbidden`. Same for revisions, heads, mission intent,
role assignment role, and event subject. Suite green through v8.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_tenant_coupled_ownership.py
python -m pytest -q
```

Result: **243 passed** (`python -m pytest -q`, 2026-07-24). Evidence recorded in UPDATES/HANDOFFS run 8.

## Changed files

- `src/holodeck_governance/storage/sqlite/migrate_v8.py`
- `src/holodeck_governance/storage/sqlite/migrations.py`
- `src/holodeck_governance/storage/sqlite/command_service.py` (reject events omit unowned subjects)
- `tests/test_governance_tenant_coupled_ownership.py`

## Residual risks

- Append-only tables reject UPDATE via v7 append-only triggers before tenant
  UPDATE triggers; INSERT cross-tenant paths are the primary adversarial proof
  for those tables.
