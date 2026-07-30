# M2-004 — Add transactional outbound collaboration-message delivery

**Status:** done
**Owner:** cursor
**Depends on:** M2-001, M2-002

## Outcome

Enqueue correlated outbound collaboration status through the M1 durable outbox,
linked to an accepted task origin and inbound receipt, without provider publish
side effects or mission/run/approval creation.

## In scope

- Persist `OutboundCollaborationMessage` with destination location refs and
  correlation fields (`task_origin_object_id`, `inbound_receipt_id`,
  `idempotency_key`).
- Application API to enqueue correlated status transactionally with an outbox
  item and domain event.
- Idempotent replay on `(tenant_id, idempotency_key)` / outbox `dedup_key`.
- Additive governance migration and tenant-coupled reference triggers.
- Tests for CIS-007 correlation, duplicate enqueue, and absent mission/run/
  approval effects.

## Non-goals

- Adapter `publish_outbound` delivery / Buzz ingress (M2-008/M2-009).
- Workspace bindings, discovery, or genesis (M2-005–M2-007).
- Typed `collaboration.outbound.enqueue` command-handler envelope (deferred;
  bootstrap/admin persistence exception continues).
- Changing `accept_task_origin` to auto-enqueue (callers enqueue explicitly).

## Required invariants

- Outbound status requires an existing same-tenant origin and matching receipt.
- One semantic idempotency key yields at most one outbound message and one
  success outbox item.
- Provider SDK types stay outside domain modules.
- Delivery acknowledgement is not modeled as human-read proof.

## Acceptance criteria

- After accepted intake, `enqueue_outbound_status` persists a correlated
  outbound message and a pending outbox item.
- Replay with the same idempotency key returns the prior message/outbox and
  creates no second row.
- Uncorrelated origin/receipt pairs are rejected.
- No mission, run, approval, or acceptance rows are created.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_outbound_delivery.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-27:

- `uv run --extra dev pytest -q tests/test_m2_outbound_delivery.py` → **4 passed**
- `uv run --extra dev pytest -q` → **290 passed in 32.21s**

Changed artifacts:

- `src/holodeck_governance/storage/sqlite/migrate_v15.py`
- `src/holodeck_governance/storage/sqlite/collaboration.py` (`enqueue_outbound_message`)
- `src/holodeck_governance/application/collaboration.py` (`enqueue_outbound_status`)
- `src/holodeck_governance/storage/sqlite/repos.py` (optional outbox item id / get_by_dedup)
- `tests/test_m2_outbound_delivery.py`
- schema-version assertions updated for governance migration v15
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-005** — Define repository/project and collaboration-location
workspace bindings.

## Residual risks

- Typed `collaboration.outbound.enqueue` command handlers remain deferred.
- Worker-side adapter publish remains M2-008/M2-009.
- M1 human acceptance and production Buzz ingress remain deferred.
