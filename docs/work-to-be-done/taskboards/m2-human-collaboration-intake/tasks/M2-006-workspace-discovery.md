# M2-006 — Implement explainable workspace discovery and eligibility evaluation

**Status:** done
**Owner:** cursor
**Depends on:** M2-003, M2-005

## Outcome

Given intake location (and optional repository) context, discover candidate
workspaces, evaluate eligibility, and select or explain why selection is
ambiguous or unbound — without creating genesis proposals.

## In scope

- Domain discovery query/result contracts with stable reason codes.
- Deterministic ranking over active location/repository bindings.
- Eligibility checks against workspace object identity/status.
- Application API `discover_workspace` that returns an explainable result.
- Tests for exact match, parent fallback, repo agreement, ambiguity, unbound,
  and ineligible workspaces.

## Non-goals

- Persisting discovery decisions or genesis proposals (M2-007).
- Full workspace intelligence readiness scoring (M2-012+).
- Adapter harness or Buzz ingress (M2-008/M2-009).
- Auto-attaching a workspace onto `accept_task_origin`.

## Required invariants

- Selection is deterministic and explainable from bindings + reason codes.
- Only active bindings contribute candidates.
- Channels/repos remain external; discovery never invents a workspace.
- Ambiguity and unbound outcomes are explicit (no silent pick).

## Acceptance criteria

- Exact location binding selects that workspace with `location.exact` evidence.
- Parent location binding can contribute a weaker candidate when exact is absent.
- Location+repository agreement ranks above location-only.
- Two eligible workspaces yield `ambiguous` with both explained.
- No candidates yield `unbound`.
- Suspended/archived workspaces are ineligible and do not silently win.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_discovery.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_workspace_discovery.py` → **6 passed**
- `uv run --extra dev pytest -q` → **302 passed in 33.33s**

Changed artifacts:

- `src/holodeck_governance/domain/workspace/discovery.py`
- `src/holodeck_governance/application/collaboration.py` (`discover_workspace`)
- `src/holodeck_governance/storage/sqlite/collaboration.py` (`get_workspace_status`)
- `tests/test_m2_workspace_discovery.py`
- this task packet and the M2 board index/lanes/updates/decisions

Next ready task: **M2-007** — Implement reversible workspace-genesis proposals
and human decision flow.

## Residual risks

- Genesis proposals for `unbound` remain M2-007.
- Richer readiness-based eligibility remains M2-012+.
