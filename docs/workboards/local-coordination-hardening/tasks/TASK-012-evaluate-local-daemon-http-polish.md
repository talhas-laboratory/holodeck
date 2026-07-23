# TASK-012-evaluate-local-daemon-http-polish: Evaluate local daemon HTTP polish

Status: backlog
Owner: unassigned
Current gate: intake

## Problem

The runtime uses Python's stdlib `ThreadingHTTPServer`. That is acceptable for alpha, but may fall short of user expectations for a polished local daemon once install and adapters exist.

## Scope

In:

- Evaluate whether stdlib HTTP remains sufficient for local loopback use after TASK-005 hardening.
- If not, choose the smallest dependency-conscious upgrade path (still local-only).
- Document the decision; implement only if friction is concrete.

Out:

- Adopting a full web framework by default.
- Remote production ASGI deployment features.

## Acceptance Criteria

- A written decision: keep stdlib HTTP, or replace with a named alternative and rationale.
- If keeping: known limits are documented (concurrency, timeouts, TLS).
- If replacing: change stays dependency-light and preserves the API contract from TASK-009.
- The decision is based on measured representative API/MCP traffic, stalled-client behavior, and graceful shutdown behavior.

## Plan

- Define pass/fail thresholds for representative API/MCP traffic, stalled requests, and graceful shutdown before evaluating alternatives.
- Revisit after TASK-005/008/009 using real adapter traffic.
- Prefer keep-and-document unless MCP/install smoke exposes real limits.
- Avoid speculative framework adoption.

## Verification Evidence

- Not run yet. Planned: run the defined local traffic, stalled-client, and shutdown checks; record measurements and the keep/replace decision. If replacing, rerun the complete API contract and MCP end-to-end suites.
- Failure mode: a framework change or a decision to retain the current server is made without evidence from the expected client workload.

## Updates

- Created: `2026-07-23T08:18:00+00:00`

## Handoff Notes

- Dependencies: TASK-005, TASK-009; optionally after TASK-010 exposes real client behavior.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G6).
