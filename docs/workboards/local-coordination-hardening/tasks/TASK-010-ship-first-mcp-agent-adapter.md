# TASK-010-ship-first-mcp-agent-adapter: Ship the first MCP agent adapter

Status: backlog
Owner: unassigned
Current gate: intake

## Problem

There is no first-class agent protocol surface. Connecting Cursor, Claude, Codex, or similar tools requires custom HTTP glue.

## Scope

In:

- An MCP server (preferred) that talks to the local Holodeck HTTP/store authority.
- Tools sufficient to inspect workspaces/tasks, begin a run with path claims, and complete a run.
- Minimal setup docs for pointing an MCP-capable client at a local Holodeck instance.
- End-to-end verification through the MCP protocol, not direct calls to adapter internals.

Out:

- Full SDK in multiple languages.
- Policy enforcement inside the adapter.
- Remote/multi-tenant MCP hosting.

## Acceptance Criteria

- A documented MCP entrypoint can list or create coordination state against a running local runtime.
- An agent can claim paths and complete a run through MCP without raw HTTP calls.
- Adapter failures map to understandable tool errors.
- Two independent MCP client sessions cannot hold overlapping active claims; completion releases only the completed run's claims.

## Plan

- Define the minimal MCP tool schemas and error mapping over the stable API.
- Implement adapter as a thin client of the local authority (no second source of truth).
- Document client configuration for at least one common MCP host.

## Verification Evidence

- Not run yet. Planned: use a real MCP client against a running local runtime to list state, begin and complete a run, validate understandable failures, and race two independent sessions for overlapping paths. Verify released claims and run state through the API afterward.
- Failure mode: direct adapter tests pass while a real MCP client, concurrent claim, or tool-error path fails.

## Updates

- Created: `2026-07-23T08:18:00+00:00`

## Handoff Notes

- Dependencies: TASK-009 for the API contract; TASK-008 for an installable runtime users can run first.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G3, G4).
