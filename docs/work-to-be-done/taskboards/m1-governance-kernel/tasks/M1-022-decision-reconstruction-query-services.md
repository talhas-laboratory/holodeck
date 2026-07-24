# M1-022: Add decision reconstruction query services

Status: backlog  
Gate: intake  
Depends on: M1-008, M1-009, M1-017, M1-018, M1-019, M1-020, M1-021  
Scenarios: GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Add application queries for exact revisions, traceability edges, command/evaluation
history, authority, policy, event timeline, external refs, and terminal decision.

## Observable acceptance

- One deterministic response explains a representative decision end to end.
- HTTP/CLI/MCP adapters expose the query without domain imports of adapter types.

## Verification

- GS-013 reconstruction fixture and adapter-to-persistence parity test.

## Non-goals

- UI or provider-specific presentation.
