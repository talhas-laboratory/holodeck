# M2-010 — Prove end-to-end authenticated intake, replay recovery, and correlated status

**Status:** done
**Owner:** cursor
**Depends on:** M2-002–M2-008

## Outcome

Prove CIS-001..008 outcomes end-to-end against the in-memory collaboration
adapter and Holodeck receipt/origin/outbox seams — without Buzz or live
provider ingress.

## In scope

- `CollaborationIntakeOrchestrator` wiring adapter normalize/verify to
  Holodeck receipt, origin, outbound enqueue, and adapter publish.
- Domain-ported `CollaborationAdapterAuthError` for CIS-001 refusal.
- E2E tests for auth failure, authorization reject, duplicate/replay,
  cross-tenant deny, non-intake ignore, and correlated accepted status without
  mission/run creation.

## Non-goals

- Live Buzz adapter or credentials (M2-009, gated).
- Workspace intelligence onboarding (M2-012+).
- Mission compilation, runs, approvals, or acceptance.
- Changing CIS scenario catalogue semantics.

## Required invariants

- Auth failure creates no Holodeck receipt/origin/outbox.
- Duplicate delivery returns prior receipt without a second origin/outbox.
- Accepted intake enqueues status correlated to origin + receipt.
- Explicit intake never creates mission/run/approval/acceptance records.
- Adapter publish ack is not proof of downstream Holodeck processing.

## Acceptance criteria

- CIS-001..008 outcomes are exercised through the memory harness orchestrator.
- Replay preserves a single origin and single outbound message.
- Happy-path outbound ack is idempotent on republish.
- Buzz remains out of scope and gated.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_e2e_memory_intake.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_e2e_memory_intake.py` → **7 passed**
- `uv run --extra dev pytest -q` → **324 passed in 32.76s**

Changed artifacts:

- `src/holodeck_governance/application/collaboration_intake.py`
- `src/holodeck_governance/domain/collaboration/adapter.py`
- `src/holodeck_governance/adapters/collaboration/memory.py`
- `src/holodeck_governance/application/collaboration.py`
- `tests/test_m2_e2e_memory_intake.py`
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-012** — Define workspace intelligence records and
contracts (Buzz M2-009 remains gated; M2-011 waits on M2-017).

## Residual risks

- Live Buzz protocol revalidation remains M2-009.
- Workspace intelligence and M3 handoff remain M2-012+ / M2-011.
