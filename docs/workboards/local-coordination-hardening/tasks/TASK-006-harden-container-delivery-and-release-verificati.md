# TASK-006-harden-container-delivery-and-release-verificati: Harden container delivery and release verification

Status: backlog
Owner: unassigned
Current gate: intake

## Problem

The container copies the whole working tree, runs as root, and the project lacks repeatable release verification.

## Scope

In:

- `.dockerignore`, deliberate image inputs, non-root runtime user, and owned writable data directory.
- Compose hardening practical for the local deployment.
- Declared development test dependency and automated package/container smoke checks.

Out:

- Digest-pinning policy automation and remote production orchestration.

## Acceptance Criteria

- Docker build context excludes `.git`, `.holodeck`, virtual environments, databases, and test caches.
- Image runs as an unprivileged user and returns a healthy endpoint with a writable `/data` volume.
- A documented command or CI workflow runs tests and a container smoke test.

## Plan

- Add ignore rules and revise Dockerfile/Compose ownership and runtime settings.
- Add a test extra or documented dev install path.
- Implement automated verification suitable for CI.

## Verification Evidence

- Not run yet. Planned: `python -m pytest -q`, package install smoke test, Docker build and `/health` check.

## Updates

- Created: `2026-07-22T17:59:34.722397+00:00`

## Handoff Notes

- Dependencies: TASK-005 defines the local binding and request behavior verified by the container.
