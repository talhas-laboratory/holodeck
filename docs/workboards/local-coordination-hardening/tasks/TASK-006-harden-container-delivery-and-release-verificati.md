# TASK-006-harden-container-delivery-and-release-verificati: Harden container delivery and release verification

Status: review
Owner: cursor
Current gate: review

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

- `python -m pytest -q` → 57 passed (2026-07-23).
- Added `.dockerignore`, hardened `Dockerfile`/`compose.yaml`, `scripts/verify_release.sh`, `.github/workflows/verify.yml`, `tests/test_release.py`.
- Dockerfile pins `python:3.13.7-slim-bookworm`; Compose adds `cap_drop: [ALL]`.
- Docker image build and `/health` smoke **not run locally** (daemon unavailable on 2026-07-23). CI workflow `container-smoke` is the current gate.
- Residual risks: container behavior unverified on this machine until `./scripts/verify_release.sh` or CI passes.

## Updates

- Created: `2026-07-22T17:59:34.722397+00:00`

## Handoff Notes

- Dependencies: TASK-005 defines the local binding and request behavior verified by the container.
