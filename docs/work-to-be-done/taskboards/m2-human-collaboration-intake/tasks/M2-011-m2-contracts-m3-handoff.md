# M2-011 — Publish M2 contracts and M3 handoff

**Status:** backlog
**Owner:** unassigned
**Depends on:** M2-010, M2-017

## Outcome

Publish the stable M2 collaboration + workspace-intelligence contracts and an
explicit handoff packet for M3 mission compilation, without expanding M2 scope
into mission/run authority.

## In scope

- Contract index for collaboration intake, workspace bindings/genesis,
  intelligence records, curation/activation, refresh/query.
- M3 handoff: what M2 guarantees, what M3 must not re-litigate, residual gaps.
- Align TASKS/README/DECISIONS with final M2 done criteria.

## Non-goals

- Implementing Buzz (M2-009).
- Compiling missions or launching agents (M3/M5).

## Required invariants

- Hand-off documents distinguish durable product vision from implemented
  behavior verified in source/tests.
- No silent expansion of Holodeck into collaboration-system identity ownership.

## Acceptance criteria

- Contracts and handoff packet reviewed and linked from the M2 board.
- M2-017 acceptance evidence recorded before marking this ready→done.

## Verification

```text
uv run --extra dev pytest -q
```

## Evidence and handoff

Pending M2-017.

## Residual risks

- Buzz still gated; handoff must not claim live provider ingress.
