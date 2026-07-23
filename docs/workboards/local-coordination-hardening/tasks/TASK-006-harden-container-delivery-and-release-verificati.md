# TASK-006-harden-container-delivery-and-release-verificati: Harden container delivery and release verification

Status: done
Owner: cursor
Current gate: done

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

- `./scripts/verify_release.sh` → 64 passed, clean package-install smoke passed, Docker image built, and container `/health` check passed (2026-07-23).
- The verifier creates and removes an isolated temporary virtual environment and source copy, avoiding the externally managed system Python and preventing package-build artifacts in the worktree.
- Post-run checks confirmed no `holodeck-verify-*` container or volume and no `build/` artifact remained.
- Added `.dockerignore`, hardened `Dockerfile`/`compose.yaml`, `scripts/verify_release.sh`, `.github/workflows/verify.yml`, `tests/test_release.py`.
- Dockerfile pins `python:3.13.7-slim-bookworm`; Compose adds `cap_drop: [ALL]`.
- Changed artifacts: `scripts/verify_release.sh`, `tests/test_release.py`.
- Residual risks: none known for the local release verifier.

## Updates

- Created: `2026-07-22T17:59:34.722397+00:00`

## Handoff Notes

- Dependencies: TASK-005 defines the local binding and request behavior verified by the container.
