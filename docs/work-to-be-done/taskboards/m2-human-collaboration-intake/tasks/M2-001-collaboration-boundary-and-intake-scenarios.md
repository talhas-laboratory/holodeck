# M2-001 — Collaboration boundary and intake scenario specification

**Status:** ready  
**Owner:** unassigned  
**Depends on:** M1 contracts/migration/M2 handoff

## Outcome

Specify the provider-neutral collaboration contract and executable acceptance
scenarios that every M2 adapter must satisfy before Buzz-specific code exists.

## In scope

- Inbound event, verified-identity, conversation-location, attachment, and
  external-reference contracts.
- Inbound receipt/checkpoint and outbound-message/idempotency contracts.
- Explicit intake-command grammar and policy inputs.
- Scenario specification for authentication, authorization, duplicate delivery,
  replay, status correlation, tenant isolation, and rejection absence.
- Mapping from the contract to M1 commands, provenance, tenant, actor, source,
  task, event, and outbox seams.

## Non-goals

- Buzz SDK or protocol implementation (M2-009).
- Context or mission compilation (M3).
- Agent execution, repository worktree provisioning, or acceptance (M4–M6).

## Required invariants

- Provider data never enters domain modules as provider-specific types.
- A receipt is unique on provider plus external event ID and preserves the
  signed source reference, verification result, and processing outcome.
- The same inbound event cannot create two governed origins or outbound actions.
- Ordinary conversation is not executable work; only explicit, authorized,
  supported intake syntax can request intake.
- Outbound status is correlated to its task origin and survives retries.

## Acceptance criteria

- A fresh builder can implement M2-002 through M2-004 without inventing wire
  contracts, authority rules, idempotency semantics, or scenario outcomes.
- The specification declares the exact expected persisted records, events,
  outbox actions, and absent writes for each canonical scenario.
- It identifies which proposed fields remain provider-adapter metadata versus
  stable Holodeck external-reference data.

## Verification

```text
uv run pytest -q tests/test_m2_collaboration_contract.py
```

The test file may initially be a contract/snapshot suite; it becomes the
implementation acceptance suite for M2-002–M2-004.

## Deliverables

- `docs/plans/<dated>-m2-collaboration-intake-design.md`
- `docs/plans/<dated>-m2-collaboration-intake-test-specification.md`
- Provider-neutral contract modules/interfaces and contract tests, if the
  existing M1 layout can host them without pre-implementing M2 persistence.

## Residual risks

Buzz implementation claims in the strategy are dated. Revalidate upstream
protocol details immediately before M2-009; do not treat this packet as proof
of current Buzz behavior.
