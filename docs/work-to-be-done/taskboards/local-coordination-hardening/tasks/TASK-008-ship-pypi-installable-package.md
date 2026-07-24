# TASK-008-ship-pypi-installable-package: Ship a PyPI-installable package

Status: done
Owner: codex
Current gate: done

## Problem

Installation today requires cloning the repo and running `pip install -e .`, which is a developer workflow rather than an end-user install path.

## Scope

In:

- Publishable package metadata and versioning suitable for PyPI.
- Documented install commands (`pip install …`, optional Docker) that do not require an editable checkout.
- Smoke check that a clean install exposes the `holodeck` CLI and can serve `/health`.
- Build and inspect the wheel and source distribution that users will actually install.

Out:

- Homebrew / single-binary packaging.
- MCP adapter (TASK-010).
- Uploading to PyPI; this is a separate owner-approved release action after package readiness is verified.

## Acceptance Criteria

- A clean virtualenv can install the package without the source tree as an editable dependency.
- `holodeck --help` (or equivalent) and `holodeck serve` work after install.
- README install section matches the published path.
- The built wheel contains required frontend/package assets and installation leaves neither the source tree nor the verification host polluted.

## Plan

- Finalize package name, entry points, version scheme, and PyPI-name availability after TASK-007.
- Add release checklist or CI publish workflow (test-first; publish when ready).
- Document Docker as optional, not required.

## Verification Evidence

- Passed: `python -m pytest -q` — 68 passed.
- Passed: `python -m compileall -q src tests` and `git diff --check`.
- Passed: `./scripts/verify_release.sh` — 68 tests; isolated sdist and wheel build; wheel installed into a separate virtual environment; `holodeck --help`, packaged frontend-asset and license inspection, and local `/health` smoke succeeded; Docker `/health` smoke succeeded; script cleaned its temporary environment, container, and volume.
- Package metadata declares the README, Python support, PyPI classifiers, keywords, canonical homepage/source/issues URLs, and `MIT OR Apache-2.0`. The published distribution name is `holodeck-control-plane`, which is unclaimed on PyPI as of `2026-07-23`; its import package and CLI are both `holodeck`.
- Failure mode covered: `tests/test_release.py` requires a separate clean wheel-install environment, installed asset inspection, and a started `holodeck` process rather than a source-tree-only install.
- Publication remains an explicitly owner-approved external action; no package was uploaded.

## Updates

- Created: `2026-07-23T08:18:00+00:00`
- Started: `2026-07-23T12:54:58+00:00`
- Ready for owner review: `2026-07-23T13:00:03+00:00`
- Completed: `2026-07-23T13:11:40+00:00`

## Handoff Notes

- Dependencies: TASK-006 for container/release smoke patterns; TASK-007 for canonical identity/URLs.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G1).
- External-release note: PyPI publication remains owner-approved; the MIT-or-Apache-2.0 licensing decision is now recorded in package metadata and both license files.
- Changed: package/import naming, `pyproject.toml`, MIT and Apache license files, README install instructions, Docker build inputs, release verification script, release tests, identity test, and `.gitignore`.
