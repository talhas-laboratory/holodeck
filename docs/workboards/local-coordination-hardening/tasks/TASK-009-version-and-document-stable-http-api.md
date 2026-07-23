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

Out:

- New product features (evidence, handoffs).
- MCP transport (TASK-010).

## Acceptance Criteria

- A single API doc lists methods, paths, request/response shapes, and error codes.
- Version identity is visible to clients (`/api/config` or equivalent).
- Breaking-change policy for the local API is stated briefly.

## Plan

- Freeze the post-hardening endpoint contract.
- Write concise API reference under `docs/`.
- Expose version metadata from the runtime config endpoint.

## Verification Evidence

- Not run yet. Planned: doc review against live `/api/*` behavior; config version field check.

## Updates

- Created: `2026-07-23T08:18:00+00:00`

## Handoff Notes

- Dependencies: TASK-005 for stable error mapping; prefer after TASK-001–004 semantics are correct.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G3).
