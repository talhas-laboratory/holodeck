# TASK-012-evaluate-local-daemon-http-polish: Evaluate local daemon HTTP polish

Status: done
Owner: codex
Current gate: done

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

- Decision: keep the hardened stdlib server; no dependency or API change is warranted for the bounded local workload.
- Measured `100` mixed `GET /health` and `GET /api/config` requests with 16 client workers: `0` errors, p95 `99.4 ms`, maximum `101.4 ms`.
- A partial request closed after `201.2 ms` with a `0.2 s` configured socket timeout; controlled server shutdown completed in `299.9 ms` and its serving thread exited.
- `python -m pytest -q tests/test_mcp_adapter.py::test_mcp_lists_runtime_and_coordinates_run --durations=1` → `1 passed`; MCP lifecycle duration `0.86 s`.
- `.venv/bin/python -m pytest -q` → `108 passed`.
- `git diff --check && .venv/bin/python -m compileall -q src tests` → passed.
- Added regression coverage for the stalled-client timeout and bounded controlled shutdown in `tests/test_http_hardening.py`; documented known limits in `README.md`.
- Residual risks: the daemon intentionally has no TLS, HTTP/2, authentication, rate limiting, or remote-production profile. Those are outside the local-only scope and require a separate product decision.

## Updates

- Created: `2026-07-23T08:18:00+00:00`
- Started evaluation: `2026-07-23T16:10:00+00:00`
- Completed: `2026-07-23T16:20:00+00:00`

## Handoff Notes

- Dependencies: TASK-005, TASK-009; optionally after TASK-010 exposes real client behavior.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G6).
- Changed artifacts: `README.md`, `tests/test_http_hardening.py`, `docs/work-to-be-done/taskboards/local-coordination-hardening/DECISIONS.md`.
