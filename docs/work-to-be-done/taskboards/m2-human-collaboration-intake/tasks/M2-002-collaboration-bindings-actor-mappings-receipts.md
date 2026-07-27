# M2-002 — Collaboration bindings, actor mappings, and durable receipts

**Status:** done
**Owner:** cursor
**Depends on:** M2-001

## Outcome

Persist provider-neutral collaboration endpoints, external actor mappings, and
idempotent inbound event receipts so authenticated ingress can be checkpointed
without creating missions, runs, approvals, or task origins.

## In scope

- Collaboration endpoint records and storage.
- External actor mapping records and storage.
- Durable `InboundEventReceipt` persistence with uniqueness on
  `(tenant_id, provider, external_event_id)`.
- Application seam for recording receipts and resolving mappings without
  provider SDK types.
- Additive governance migration for the new tables.
- Tests for duplicate delivery, tenant isolation on bindings/receipts, and
  rejected/ignored receipt persistence without task origins.

## Non-goals

- Task origin recording (M2-003).
- Outbound collaboration delivery (M2-004).
- Repository/project or collaboration-location workspace bindings (M2-005).
- Workspace discovery/genesis (M2-006/M2-007).
- Buzz adapter or live ingress (M2-009).

## Required invariants

- Provider SDK/protocol types stay outside domain and storage row shapes.
- Receipt replay returns the prior durable receipt and creates no second row.
- Binding and receipt writes remain tenant-scoped.
- Recording a receipt never creates mission, run, approval, acceptance, or
  task-origin rows.

## Acceptance criteria

- A builder can resolve an external actor mapping and record/replay an inbound
  receipt against durable storage.
- Duplicate external events do not create a second receipt row.
- Cross-tenant mapping or receipt attempts are rejected.
- CIS receipt write-set expectations for rejected/ignored/duplicate paths remain
  consistent with the M2-001 catalogue (no origin/outbox success effects).

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_collaboration_bindings_receipts.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-27:

- `uv run pytest -q tests/test_m2_collaboration_bindings_receipts.py` → **8 passed**
- `uv run pytest -q` → **276 passed in 31.10s**

Changed artifacts:

- `src/holodeck_governance/domain/collaboration/bindings.py`
- `src/holodeck_governance/application/collaboration.py`
- `src/holodeck_governance/storage/sqlite/migrate_v11.py`
- `src/holodeck_governance/storage/sqlite/collaboration.py`
- `src/holodeck_governance/composition.py` (`open_collaboration_app`)
- `tests/test_m2_collaboration_bindings_receipts.py`
- schema-version assertions updated for governance migration v11
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-003** — Record task origins and source-thread context
through the M1 application seam.

## Residual risks

- Typed `collaboration.*.record` command handlers remain deferred; M2-002 uses
  the bootstrap/admin persistence exception via `open_collaboration_app`.
- Task origins and outbound delivery are intentionally unimplemented.
- M1 human acceptance and production Buzz ingress remain deferred.
