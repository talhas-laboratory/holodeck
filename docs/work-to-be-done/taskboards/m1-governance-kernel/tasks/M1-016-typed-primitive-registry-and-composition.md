# M1-016: Add typed primitive registry and composition

Status: backlog  
Gate: intake  
Depends on: M1-007, M1-012, M1-013, M1-014, M1-015  
Scenarios: foundation for GS-003, GS-004, GS-008, GS-009, GS-011

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement code-defined typed governance primitives and internal `all`, `any`,
and `at_least` composition with a fixed trusted registry.

## Observable acceptance

- Unknown primitives and incompatible inputs fail validation.
- No generic `not`, arbitrary field/query operation, or stored executable code exists.

## Verification

- Primitive contract tests and invalid-registry/composition cases.

## Non-goals

- Persisted snapshots, policy configuration, or a rule DSL.
