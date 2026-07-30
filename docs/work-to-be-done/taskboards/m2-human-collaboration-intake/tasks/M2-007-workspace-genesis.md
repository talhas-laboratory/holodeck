# M2-007 — Implement reversible workspace-genesis proposals and human decision flow

**Status:** done
**Owner:** cursor
**Depends on:** M2-003, M2-005, M2-006

## Outcome

When workspace discovery is unbound, record a reversible workspace-genesis
proposal and apply an explicit human decision (approve, reject, or withdraw)
without treating chat as the system of record.

## In scope

- `WorkspaceGenesisProposal` domain record with status lifecycle.
- Additive persistence and tenant-coupled references.
- Application APIs: `propose_workspace_genesis`, `decide_workspace_genesis`,
  `get_workspace_genesis_proposal`.
- On approve: register a Workspace object, persist a workspace record, and
  activate a collaboration-location binding (optional repository binding).
- On reject/withdraw: close the proposal without creating a workspace.
- Tests for unbound→propose, approve creates binding, reject/withdraw leave no
  workspace, duplicate open proposal denial, and cross-tenant rejection.

## Non-goals

- Full intelligence onboarding (model sections, readiness levels) — M2-012+.
- Adapter harness or Buzz decision capture UI — M2-008/M2-009.
- Auto-propose inside `accept_task_origin`.
- Mission/run creation.

## Required invariants

- Genesis is proposed, not silently executed.
- Proposals remain reversible until a human decision is recorded.
- Approve is the only path that creates a workspace + active location binding.
- Tenant isolation holds for endpoint, location refs, actors, and workspace.
- Provider SDK types stay outside domain modules.

## Acceptance criteria

- Unbound discovery context can open one proposed genesis proposal per location
  natural key.
- Approve creates a queryable workspace and active location binding.
- Reject and withdraw create no workspace/binding and close the proposal.
- A second open proposal for the same location is rejected.
- Cross-tenant proposal attempts are rejected.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_genesis.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_workspace_genesis.py` → **7 passed**
- `uv run --extra dev pytest -q` → **309 passed**

Changed artifacts:

- `src/holodeck_governance/domain/workspace/genesis.py`
- `src/holodeck_governance/storage/sqlite/migrate_v17.py`
- `src/holodeck_governance/storage/sqlite/migrations.py`
- `src/holodeck_governance/storage/sqlite/collaboration.py`
- `src/holodeck_governance/application/collaboration.py`
- `tests/test_m2_workspace_genesis.py`
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-008** — Implement a provider-neutral in-memory adapter
test harness.

## Residual risks

- Richer intent-seed / readiness onboarding remains M2-012+.
- Signed external decision capture via Buzz remains M2-009.
- Adapter publish / harness remains M2-008.
