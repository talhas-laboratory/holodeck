# TASK-005-harden-http-validation-and-local-exposure: Harden HTTP validation and local exposure

Status: done
Owner: cursor
Current gate: done

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

- `python -m pytest -q` → 34 passed (2026-07-23).
- Added `tests/test_http_hardening.py` for 404/409/422/400/415 mapping, identifier validation, and bind policy.
- Changed files: `src/holodeck_runtime/http_request.py`, `src/holodeck_runtime/service.py`, `src/holodeck_runtime/cli.py`, `Dockerfile`.
- Residual risks: ContentionError → 503 is implemented but not stress-tested under real lock contention.

## Updates

- Created: `2026-07-22T17:59:34.722300+00:00`

## Handoff Notes

- Dependencies: TASK-001 through TASK-004 provide the errors and validation this adapter exposes.
