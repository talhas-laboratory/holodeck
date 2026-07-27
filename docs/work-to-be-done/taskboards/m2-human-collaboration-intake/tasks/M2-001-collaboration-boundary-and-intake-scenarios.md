# M2-001 — Collaboration boundary and intake scenario specification

**Status:** done  
**Owner:** cursor  
**Depends on:** M2-000

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
- Persistent M2 records, repository discovery, or workspace intelligence
  behavior (later M2 packets).

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
uv run pytest -q
```

## Evidence and handoff

Verification completed 2026-07-27:

- `uv run pytest -q tests/test_m2_collaboration_contract.py` → **15 passed in 0.06s**
- `uv run pytest -q` → **268 passed in 32.52s**

Changed artifacts:

- `docs/plans/2026-07-27-m2-collaboration-intake-design.md`
- `docs/plans/2026-07-27-m2-collaboration-intake-test-specification.md`
- `src/holodeck_governance/domain/collaboration/` (provider-neutral contracts)
- `tests/test_m2_collaboration_contract.py`
- this task packet and the M2 board index, lanes, decisions, and updates

Next ready task: **M2-002** — Add collaboration bindings, external actor
mappings, and durable event receipts.

## Residual risks

- Buzz implementation claims in the strategy are dated. Revalidate upstream
  protocol details immediately before M2-009.
- M1-024 and M1-025 remain in review; production Buzz ingress stays deferred.
- Contractual command type names are fixed for builders; storage packing may
  refine in M2-002 without changing CIS scenario outcomes.
