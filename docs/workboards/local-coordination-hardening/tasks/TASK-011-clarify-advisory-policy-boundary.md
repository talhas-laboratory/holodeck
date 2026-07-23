# TASK-011-clarify-advisory-policy-boundary: Clarify advisory policy boundary

Status: backlog
Owner: unassigned
Current gate: intake

## Problem

`.holodeck/policy.json` reads like a sandbox, but the runtime does not enforce those actions. Users may assume Holodeck blocks writes, network, or deploys.

## Scope

In:

- Explicit documentation that onboarding policy is advisory until enforcement adapters exist.
- Dashboard/config copy that does not imply runtime authorization.
- Decision record for when enforcement becomes in-scope.

Out:

- Building enforcement adapters, OS sandboxing, or tool-call auditing.

## Acceptance Criteria

- README and config UI/docs state policy is advisory.
- `holodeck policy-check` help/docs describe decision lookup, not enforcement.
- `DECISIONS.md` records the enforcement deferral and trigger conditions.

## Plan

- Audit user-facing strings for over-claiming.
- Update docs and capability ledger wording if needed.
- Record deferral decision with a clear “revisit when” note.

## Verification Evidence

- Not run yet. Planned: doc/UI string review; capability ledger check.

## Updates

- Created: `2026-07-23T08:18:00+00:00`

## Handoff Notes

- Dependencies: none strict; best done before public launch messaging.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G5).
