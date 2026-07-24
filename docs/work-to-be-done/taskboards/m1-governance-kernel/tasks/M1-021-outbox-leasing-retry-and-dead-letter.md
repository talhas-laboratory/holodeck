# M1-021: Add outbox leasing, retry, and dead-letter escalation

Status: backlog  
Gate: intake  
Depends on: M1-020  
Scenarios: GS-012

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Scope

Implement lease acquisition/recovery, append-only attempts, exponential backoff,
bounded retries, recipient dedup key, dead-letter state, and escalation record.

## Observable acceptance

- A crashed lease holder cannot permanently strand work.
- Duplicate delivery preserves one recipient effect.
- Exhaustion records dead letter and escalation without reversing the decision.

## Verification

- Complete GS-012 clock-controlled worker recovery fixture.

## Non-goals

- Buzz or other concrete delivery drivers.
