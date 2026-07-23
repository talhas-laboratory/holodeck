# TASK-008-ship-pypi-installable-package: Ship a PyPI-installable package

Status: backlog
Owner: unassigned
Current gate: intake

## Problem

Installation today requires cloning the repo and running `pip install -e .`, which is a developer workflow rather than an end-user install path.

## Scope

In:

- Publishable package metadata and versioning suitable for PyPI.
- Documented install commands (`pip install …`, optional Docker) that do not require an editable checkout.
- Smoke check that a clean install exposes the `holodeck` CLI and can serve `/health`.

Out:

- Homebrew / single-binary packaging.
- MCP adapter (TASK-010).

## Acceptance Criteria

- A clean virtualenv can install the package without the source tree as an editable dependency.
- `holodeck --help` (or equivalent) and `holodeck serve` work after install.
- README install section matches the published path.

## Plan

- Finalize package name, entry points, and version scheme.
- Add release checklist or CI publish workflow (test-first; publish when ready).
- Document Docker as optional, not required.

## Verification Evidence

- Not run yet. Planned: clean venv install smoke test; CLI + `/health`.

## Updates

- Created: `2026-07-23T08:18:00+00:00`

## Handoff Notes

- Dependencies: TASK-006 for container/release smoke patterns; TASK-007 for canonical identity/URLs.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G1).
