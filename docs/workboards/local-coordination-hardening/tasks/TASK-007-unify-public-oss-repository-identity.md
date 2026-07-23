# TASK-007-unify-public-oss-repository-identity: Unify public OSS repository identity

Status: done
Owner: codex
Current gate: done

## Problem

The legacy runtime URL and dual-push setup confuse install docs, contributors, and the project's public identity.

## Scope

In:

- Choose one canonical GitHub repository for OSS.
- Align README, package metadata, and clone/install instructions to that identity.
- Document what happens to the secondary remote (archive, redirect note, or mirror policy).

Out:

- PyPI publishing mechanics (TASK-008).
- API or adapter work.

## Acceptance Criteria

- One repository is declared canonical in README and package metadata.
- Contributor and install docs do not require knowing about a second remote.
- Secondary remote disposition is recorded in `DECISIONS.md`.
- The local canonical remote has exactly one push URL; no ordinary push updates the secondary repository unintentionally.

## Plan

- Decide canonical name (`holodeck` preferred unless packaging conflicts) and secondary disposition before changing remotes.
- Update docs and `pyproject.toml` URLs.
- Record mirror/archive decision for the secondary remote and apply it only with owner approval.

## Verification Evidence

- The former repository URL resolves to repository id `1301599849`, `talhas-laboratory/holodeck`; the old name is already a GitHub redirect, not a separate repository that can be archived safely.
- `git remote -v` and `git config --get-all remote.origin.pushurl` confirm that `origin` has one fetch URL and one push URL, both pointing to `https://github.com/talhas-laboratory/holodeck.git`; the stale `runtime` remote was removed.
- `python -m pytest -q tests/test_project_identity.py` verifies that README and `pyproject.toml` name only the canonical public repository.
- Changed artifacts: `README.md`, `pyproject.toml`, `tests/test_project_identity.py`, `docs/plans/2026-07-23-oss-adoption-gaps.md`, `docs/workboards/local-coordination-hardening/DECISIONS.md`.
- Residual risks: none known. The requested archive action is already represented by GitHub's legacy-name redirect; attempting an archive would target the canonical repository.

## Updates

- Created: `2026-07-23T08:18:00+00:00`

## Handoff Notes

- Dependencies: none beyond completing TASK-001–006 before cutting an OSS release; identity work may start in parallel after hardening begins.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G2).
