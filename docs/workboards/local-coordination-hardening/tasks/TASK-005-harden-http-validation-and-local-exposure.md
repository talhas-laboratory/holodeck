# TASK-005-harden-http-validation-and-local-exposure: Harden HTTP validation and local exposure

Status: backlog
Owner: unassigned
Current gate: intake

## Problem

The HTTP adapter accepts unsafe request shapes, maps most errors to `400`, and permits accidental network exposure.

## Scope

In:

- Bounded JSON request parsing, content-type checks, and URL-safe identifiers.
- Stable HTTP error mapping and SQLite contention response.
- Loopback-only default with explicit insecure non-loopback opt-in.

Out:

- Authentication, authorization, rate limiting, and remote multi-agent support.

## Acceptance Criteria

- Invalid JSON, body length, content type, body size, and non-object payloads return correct client errors.
- Missing, conflicting, invalid, and busy resources return `404`, `409`, `422`, and `503` respectively.
- Non-loopback binding is rejected unless explicitly opted into insecure operation.

## Plan

- Add reusable request and domain-error handling.
- Map store exceptions to the API contract.
- Add HTTP integration tests for malformed and conflicting requests.

## Verification Evidence

- Not run yet. Planned: HTTP pytest integration cases.

## Updates

- Created: `2026-07-22T17:59:34.722300+00:00`

## Handoff Notes

- Dependencies: TASK-001 through TASK-004 provide the errors and validation this adapter exposes.
