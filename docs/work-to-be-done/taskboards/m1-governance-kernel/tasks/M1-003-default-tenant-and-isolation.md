# M1-003: Add default-local tenant and tenant isolation

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-001, M1-002  
Scenarios: GS-001


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

## Scope

Create the tenant record, bootstrap one default local tenant, and require a
tenant key on existing workspace/task/run ownership paths.

## Verification

`python -m pytest -q tests/test_governance_tenant.py` and full suite (144 passed).

## Changed files

- `src/holodeck_governance/domain/tenant.py`
- `src/holodeck_governance/storage/sqlite/migrations.py`
- `src/holodeck_governance/storage/sqlite/tenants.py`
- `src/holodeck_governance/storage/protocols.py`
- `tests/test_governance_tenant.py`

## Residual risks

- Legacy M0 tables are not yet tenant-keyed; additive FK wiring lands with
  migration packets (M1-006/M1-023). Domain isolation helper is enforced now.
- none known beyond that deferred wiring

## Non-goals

- External organization discovery or multi-tenant administration UI.
