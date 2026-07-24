# M1-024: Prove all integrated governance scenarios

Status: backlog  
Gate: intake  
Depends on: M1-003 through M1-023  
Scenarios: GS-001 through GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement the canonical fixture builders and run every governance scenario
through the actual command, database, evaluator, event/outbox, and query seams.

## Observable acceptance

- Every GS scenario passes with exact reason codes and expected presence/absence.
- The full existing regression suite remains green.
- Failures name the owning task rather than being hidden by fixture setup.

## Verification

- Run the complete scenario suite twice, including isolated concurrency and migration fixtures.

## Non-goals

- Adding behavior solely to make a test pass outside the approved M1 design.
