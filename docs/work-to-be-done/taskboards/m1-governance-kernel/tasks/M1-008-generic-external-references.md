# M1-008: Add generic external references

Status: backlog  
Gate: intake  
Depends on: M1-003, M1-004, M1-007  
Scenarios: supports GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement provider-neutral external object type/ID, locator, integrity metadata,
observed time, and tenant-bound subject linkage.

## Observable acceptance

- Platform-specific IDs never become kernel primary keys.
- Duplicate provider/object IDs resolve idempotently within a tenant.

## Verification

- External-reference uniqueness, integrity, and tenant-isolation tests.

## Non-goals

- Buzz, GitHub, CI, or other provider adapters.
