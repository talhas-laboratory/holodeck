# Decisions

## 2026-07-27 — M2 boundary and implementation order

- M2 begins with a provider-neutral collaboration contract and executable
  scenario specification; Buzz is the first adapter only after that seam exists.
- An authenticated external event creates a durable, idempotent task origin.
  It does not by itself authorize a mission, run, or acceptance decision.
- Workspace selection is deterministic and explainable. New workspace creation
  remains a reversible proposal until the relevant authorized human decision.
- M2 publishes correlated status through the existing durable-outbox pattern;
  delivery acknowledgement is not proof of downstream processing.

## 2026-07-27 — Guarded M2 start against reviewed M1 handoff

- M1's implementation and M2 handoff artifact are available, but M1-024 and
  M1-025 remain in review pending human milestone acceptance.
- M2 may begin provider-neutral contract, workspace-intelligence, persistence,
  and test-harness work against that reviewed handoff.
- Production Buzz ingress and any external side-effecting provider deployment
  remain deferred until M1 is human-accepted or a later explicit exception
  authorizes them.
- The workspace model is defined by
  `docs/plans/2026-07-27-workspace-model-and-intelligence-design.md`; M2 must
  implement it progressively rather than reducing a workspace to a repository
  locator and name.
