# M2-003 — Record task origins and source-thread context

**Status:** done  
**Owner:** cursor  
**Depends on:** M2-001, M2-002

## Outcome

Record a durable, idempotent task origin and its source-thread context for an
explicit authorized intake event, without creating missions, runs, approvals,
or outbound status delivery.

## In scope

- `TaskOrigin` domain record including source-thread context.
- Additive persistence and repository/application APIs to accept intake origins.
- Link accepted inbound receipts to the created origin object id.
- Idempotent replay: duplicate external events do not create a second origin.
- Tests covering happy-path origin creation, duplicate replay, tenant isolation,
  and absence of mission/run/approval/outbox success effects.

## Non-goals

- Outbound collaboration delivery (M2-004).
- Workspace bindings, discovery, or genesis (M2-005–M2-007).
- Buzz adapter or live ingress (M2-009).
- Mission compilation or acceptance (M3/M6).

## Required invariants

- External messages remain task origins, never missions/approvals/runs.
- One inbound receipt maps to at most one task origin.
- Origin writes stay tenant-scoped and reference durable source/location refs.
- Provider SDK types stay outside domain modules.

## Acceptance criteria

- Explicit authorized intake persists a queryable task origin with source-thread
  context and links the inbound receipt.
- Replay of the same external event returns the prior origin and receipt.
- No mission, run, approval, acceptance, or success outbox rows are created.

## Verification

```text
uv run pytest -q tests/test_m2_task_origins.py
uv run pytest -q
```

## Evidence and handoff

Verification completed 2026-07-27:

- `uv run pytest -q tests/test_m2_task_origins.py` → **5 passed**
- `uv run pytest -q` → **281 passed in 30.38s**

Changed artifacts:

- `src/holodeck_governance/domain/collaboration/origins.py`
- `src/holodeck_governance/storage/sqlite/migrate_v12.py`
- `src/holodeck_governance/storage/sqlite/collaboration.py`
- `src/holodeck_governance/application/collaboration.py` (`accept_task_origin`)
- `tests/test_m2_task_origins.py`
- schema-version assertions updated for governance migration v12
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-004** — Add transactional outbound collaboration-message
delivery.

## Residual risks

- Typed `collaboration.origin.record` command handlers remain deferred.
- Outbound correlated status is intentionally unimplemented until M2-004.
- M1 human acceptance and production Buzz ingress remain deferred.
