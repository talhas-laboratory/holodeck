# M2-008 — Implement a provider-neutral in-memory adapter test harness

**Status:** done
**Owner:** cursor
**Depends on:** M2-001–M2-007

## Outcome

Ship a replaceable in-memory `CollaborationAdapter` that normalizes inbound
events, verifies/maps actors, and publishes outbound acknowledgements without
Buzz or any live provider SDK — the reference harness for CIS auth/outbound
paths and for M2-009.

## In scope

- `InMemoryCollaborationAdapter` implementing `CollaborationAdapter`.
- Adapter-local auth refusal for unsigned/invalid signatures and unknown actors.
- Configured external-actor directory and deterministic outbound mailbox with
  idempotent republish.
- Package placement under `holodeck_governance.adapters` (outside domain).
- Tests for normalize, auth refusal, verify/map, outbound idempotency, and
  domain/adapters boundary.

## Non-goals

- Buzz SDK, credentials, or live ingress (M2-009).
- Full CIS persistence E2E through receipts/origins/outbox (M2-010).
- Signed decision capture UI.
- Mission/run/acceptance creation.

## Required invariants

- Provider SDK types stay out of domain modules.
- Auth failure refuses a trusted tenant event (no Holodeck receipt required).
- Outbound delivery ack is not proof of downstream Holodeck processing.
- Republishing the same outbound idempotency key does not duplicate the
  semantic mailbox entry.
- Domain must not import the adapters package.

## Acceptance criteria

- Memory adapter satisfies the `CollaborationAdapter` protocol.
- Verified signed payloads normalize to provider-neutral inbound events.
- Unsigned/invalid signatures and unknown actors raise adapter-local auth
  errors with `unsigned` / `failed` results.
- Outbound publish returns an ack and is idempotent on `idempotency_key`.
- Domain collaboration package imports no adapters modules.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_memory_adapter_harness.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_memory_adapter_harness.py` → **8 passed**
- `uv run --extra dev pytest -q` → **317 passed in 33.23s**

Changed artifacts:

- `src/holodeck_governance/adapters/collaboration/memory.py`
- `src/holodeck_governance/domain/vocabulary.py` (forbid domain→adapters imports)
- `tests/test_m2_memory_adapter_harness.py`
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-009** — Implement the first Buzz adapter behind the
neutral collaboration boundary (still deferred for live ingress until gated).

## Residual risks

- Buzz protocol claims remain dated until revalidated in M2-009.
- End-to-end CIS persistence through adapter + application remains M2-010.
- Production Buzz ingress remains deferred under the guarded M1 start decision.
