# TASK-009-version-and-document-stable-http-api: Version and document the stable HTTP API

Status: backlog
Owner: unassigned
Current gate: intake

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

- Not run yet. Planned: run contract tests against a live server and compare every documented endpoint, request shape, response shape, status code, and version marker; include concurrent claim conflict and state-transition failures.
- Failure mode: docs, config metadata, and live HTTP behavior drift apart.

## Updates

- Created: `2026-07-23T08:18:00+00:00`

## Handoff Notes

- Dependencies: TASK-005 for stable error mapping; prefer after TASK-001–004 semantics are correct.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G3).
