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
