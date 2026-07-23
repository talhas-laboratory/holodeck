# TASK-009-version-and-document-stable-http-api: Version and document the stable HTTP API

Status: done
Owner: cursor
Current gate: done

## Problem

Agents and tools can only connect by reverse-engineering the current HTTP surface; there is no versioned contract to build against.

## Scope

In:

- Document the alpha/stable endpoint set for workspaces, tasks, runs, claims, health, and config.
- Add an explicit API version marker (header, path prefix, or documented schema version).
- Align error shapes with the hardened HTTP mapping from TASK-005.
- Maintain one machine-checkable contract or compatibility fixture that tests the documented behavior against a live server.

Out:

- New product features (evidence, handoffs).
- MCP transport (TASK-010).

## Acceptance Criteria

- A single API doc lists methods, paths, request/response shapes, and error codes.
- Version identity is visible to clients (`/api/config` or equivalent).
- Breaking-change policy for the local API is stated briefly.
- Contract tests cover success, malformed input, missing resources, conflicts, lifecycle violations, and server-contention responses for every public endpoint.

## Plan

- Freeze the post-hardening endpoint contract and choose one versioning mechanism.
- Write concise API reference under `docs/`.
- Expose version metadata from the runtime config endpoint and test it through HTTP.

## Verification Evidence

- `python -m pytest -q` → 79 passed (2026-07-23).
- Added `docs/http-api-v1.md`, `src/holodeck/api.py`, and `tests/test_api_contract.py`.
- `GET /api/config` exposes `api.version`, `api.stability`, `api.contract`, and breaking-change policy text.
- Contract tests cover health, config, workspaces, tasks, runs, claims, 404/409/422/503 paths, and documentation file presence.
- Residual risks: alpha contract may gain additive fields; breaking changes require `api.version` bump per documented policy.

## Updates

- Created: `2026-07-23T08:18:00+00:00`
- Completed: `2026-07-23T15:30:00+00:00`

## Handoff Notes

- Dependencies: TASK-005 for stable error mapping; prefer after TASK-001–004 semantics are correct.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G3 partially addressed; TASK-010 still needed for agent adapter).
- TASK-010 should import `api.version` from `/api/config` and target `http-api-v1`.
