# M1-003: Add default-local tenant and tenant isolation

Status: backlog  
Gate: intake  
Depends on: M1-001, M1-002  
Scenarios: GS-001

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Create the tenant record, bootstrap one default local tenant, and require a
tenant key on existing workspace/task/run ownership paths.

## Observable acceptance

- Fresh and upgraded databases contain exactly one default tenant.
- A cross-tenant ownership reference fails at the domain and database boundary.

## Verification

- Fresh-schema, upgrade, and cross-tenant rejection tests for GS-001.

## Non-goals

- External organization discovery or multi-tenant administration UI.
