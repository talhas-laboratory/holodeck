# M2-000 — Establish M2 entry readiness and workspace-model contract

**Status:** done  
**Owner:** codex  
**Depends on:** M1-025 handoff artifact

## Outcome

M2 starts from a verified M1 handoff and an approved, implementation-ready
workspace-model boundary. The board contains the required workspace-intelligence
work instead of treating a workspace as only a repository locator.

## Scope

- Verify the current M1 migration, test, application, tenant, provenance, and
  outbox baseline named in the M2 handoff artifact.
- Record the explicit guarded-start decision while M1 remains in human review.
- Establish the workspace-model design as the authority for M2 intelligence
  work.
- Expand the M2 task index for intelligence records, persistence, discovery,
  curation/readiness, refresh/query APIs, and onboarding proof.
- Define the conditions that must hold before M2-001 begins.

## Non-goals

- Implement a collaboration provider, repository scanner, or workspace
  persistence behavior.
- Treat M1 as human-accepted.
- Launch agents, provision execution environments, or compile missions.

## Required entry conditions for M2-001

1. `uv run pytest -q` passes from the current checkout.
2. M1 migrations are verified through v10 and the M1 application seam is
   available through `open_governance_app`.
3. The guarded-start decision is recorded: only provider-neutral M2 work may
   proceed while M1 acceptance remains pending.
4. The workspace-model design names stable entities, authority boundaries,
   readiness semantics, and the M2/M3 handoff.
5. The M2 index has explicit follow-on packets for workspace intelligence.

## Acceptance criteria

- Every required entry condition has direct, recorded evidence.
- The M2 board, decision log, update history, and this packet agree.
- A builder can start M2-001 without assuming that a repository URL is a
  workspace or that provider-specific types may enter the domain.
- The remaining risk—M1 human acceptance—is explicit and bounded.

## Verification

```text
uv run pytest -q
test -f docs/plans/2026-07-27-workspace-model-and-intelligence-design.md
rg -n "M2-012|M2-017" docs/work-to-be-done/taskboards/m2-human-collaboration-intake/TASKS.md
```

## Evidence and handoff

Verification completed 2026-07-27:

- `uv run pytest -q` → **253 passed in 31.60s**.
- `src/holodeck_governance/storage/sqlite/migrations.py` registers migration
  v10, `authority_issuance_basis`.
- `holodeck_governance.composition.open_governance_app` remains the M1 adapter
  application seam.
- The workspace-model design exists and `TASKS.md` contains M2-012 through
  M2-017.

Changed artifacts:

- `docs/plans/2026-07-27-workspace-model-and-intelligence-design.md`
- this task packet and the M2 board README, task index, decisions, updates, and
  lane placement.

Next ready task: M2-001, collaboration boundary and intake scenario
specification.

## Residual risk

M1-024 and M1-025 remain in review. Production Buzz ingress is deliberately
out of scope until human M1 acceptance or a recorded exception.
