# M2-005 — Define repository/project and collaboration-location workspace bindings

**Status:** done
**Owner:** cursor
**Depends on:** M2-002

## Outcome

Establish durable, tenant-safe bindings that connect repositories/projects and
collaboration locations to Holodeck workspaces, with explicit status,
provenance, ownership, and deterministic lookup for intake.

## In scope

- `RepositoryBinding` and `CollaborationLocationBinding` domain records.
- Additive persistence with uniqueness, tenant-coupled references, and status.
- Application APIs to save bindings and resolve the active workspace for a
  repository or collaboration location.
- Tests for happy-path lookup, duplicate natural keys, cross-tenant denial,
  and inactive (proposed/retired) bindings not resolving for intake.

## Non-goals

- Explainable multi-candidate workspace selection (M2-006).
- Workspace-genesis proposals when no binding matches (M2-007).
- In-memory adapter harness or Buzz ingress (M2-008/M2-009).
- Full workspace intelligence models, readiness, or source curation (M2-012+).

## Required invariants

- A repository or collaboration location may be bound to a workspace but is
  never itself the workspace.
- Bindings are tenant-scoped; cross-tenant workspace or endpoint references are
  rejected.
- Intake lookup is deterministic: at most one active binding per natural key.
- Only `active` bindings resolve for intake; `proposed` and `retired` do not.
- Provider SDK types stay outside domain modules.

## Acceptance criteria

- A builder can persist repository and collaboration-location bindings with
  status, provenance, and ownership.
- Active bindings resolve deterministically to a workspace object id.
- Inactive bindings and cross-tenant attempts do not resolve / are rejected.
- Natural-key uniqueness prevents ambiguous active mappings.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_bindings.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_workspace_bindings.py` → **6 passed**
- `uv run --extra dev pytest -q` → **296 passed in 31.97s**

Changed artifacts:

- `src/holodeck_governance/domain/workspace/` (`RepositoryBinding`,
  `CollaborationLocationBinding`, `WorkspaceBindingStatus`)
- `src/holodeck_governance/storage/sqlite/migrate_v16.py`
- `src/holodeck_governance/storage/sqlite/collaboration.py` (save/resolve/status)
- `src/holodeck_governance/application/collaboration.py`
  (`resolve_workspace_by_repository`, `resolve_workspace_by_collaboration_location`)
- `tests/test_m2_workspace_bindings.py`
- schema-version assertions updated for governance migration v16
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-006** — Implement explainable workspace discovery and
eligibility evaluation.

## Residual risks

- Multi-binding eligibility ranking remains M2-006.
- Genesis when unbound remains M2-007.
- Intake auto-resolution wiring into `accept_task_origin` remains a later
  composition choice once discovery exists.
