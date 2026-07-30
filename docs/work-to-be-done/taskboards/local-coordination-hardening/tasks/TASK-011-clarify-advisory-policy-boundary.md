# TASK-011-clarify-advisory-policy-boundary: Clarify advisory policy boundary

Status: done
Owner: codex
Current gate: done

## Problem

`.holodeck/policy.json` reads like a sandbox, but the runtime does not enforce those actions. Users may assume Holodeck blocks writes, network, or deploys.

## Scope

In:

- Explicit documentation that onboarding policy is advisory until enforcement adapters exist.
- Dashboard/config copy that does not imply runtime authorization.
- Decision record for when enforcement becomes in-scope.
- A machine-readable capability field identifying policy enforcement as `advisory`.

Out:

- Building enforcement adapters, OS sandboxing, or tool-call auditing.

## Acceptance Criteria

- README and config UI/docs state policy is advisory.
- `holodeck policy-check` help/docs describe decision lookup, not enforcement.
- `DECISIONS.md` records the enforcement deferral and trigger conditions.
- API/config output, CLI help, and visible dashboard text consistently state the same advisory boundary.

## Plan

- Audit user-facing strings and API/config output for over-claiming.
- Update docs and capability ledger wording if needed.
- Record deferral decision with a clear “revisit when” note.

## Verification Evidence

- Passed: `python -m pytest -q` — 66 passed, including the new cross-surface policy-boundary test.
- Passed: `python -m compileall -q src tests` and `git diff --check`.
- API/config: `/api/config` exposes `policy_enforcement: "advisory"`; the capability ledger calls it “Advisory project onboarding policy”.
- CLI: `holodeck policy-check --help` says it looks up an advisory decision and does not enforce or block actions.
- Documentation: README and architecture documentation explicitly say the policy does not intercept, enforce, or block actions.
- Dashboard: live local runtime at `http://127.0.0.1:8788/`, Configuration view, visibly showed “advisory” and “These settings are advisory: they do not enforce or block actions.” Browser console had no warnings or errors.
- Failure mode covered: `tests/test_policy_boundary.py` fails when the CLI, README, or visible dashboard copy loses the advisory boundary.
- Residual risk: policy still has no enforcement effect by design. This task discloses that boundary; actual enforcement remains a separately scoped future milestone.

## Updates

- Created: `2026-07-23T08:18:00+00:00`
- Completed: `2026-07-23T12:54:58+00:00`

## Handoff Notes

- Dependencies: none strict; complete before public package publication or MCP onboarding documentation.
- Report: `docs/plans/2026-07-23-oss-adoption-gaps.md` (G5).
- Changed: `service.py`, `cli.py`, dashboard copy, README, architecture documentation, and `tests/test_policy_boundary.py`.
- Enforcement is deliberately not implemented here; revisit only when a tool/adapter mediation point and auditable approval model are in scope.
