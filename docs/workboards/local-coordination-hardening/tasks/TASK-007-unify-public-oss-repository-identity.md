# TASK-007-unify-public-oss-repository-identity: Unify public OSS repository identity

Status: backlog
Owner: unassigned
Current gate: intake

## Problem

Two public remotes (`holodeck` and `holodeck-runtime`) and dual-push setup confuse install docs, contributors, and the project's public identity.

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

## Plan

- Decide canonical name (`holodeck` preferred unless packaging conflicts).
- Update docs and `pyproject.toml` URLs.
- Record mirror/archive decision for the secondary remote.

## Verification Evidence

- Not run yet. Planned: README + `pyproject.toml` review; `gh repo view` on canonical remote.

## Updates

- Created: `2026-07-23T08:18:00+00:00`

## Handoff Notes

- Dependencies: none beyond completing TASK-001–006 before cutting an OSS release; identity work may start in parallel after hardening begins.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G2).
