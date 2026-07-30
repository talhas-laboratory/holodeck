# M2-009 — Implement the first Buzz adapter

**Status:** blocked
**Owner:** unassigned
**Depends on:** M2-001–M2-008

## Outcome

First replaceable Buzz collaboration adapter behind the provider-neutral
`CollaborationAdapter` boundary, preserving Holodeck ownership of workspaces,
missions, evidence, and acceptance.

## Blocked because

- Live Buzz ingress requires human acceptance of auth/membership mapping and
  environment credentials.
- Provider-neutral contracts + memory harness (M2-008) and e2e memory proof
  (M2-010) are prerequisites; onboarding/refresh acceptance (M2-017) should
  remain independent of Buzz.

## In scope (when unblocked)

- Buzz adapter implementing normalize/verify/publish (+ optional
  `fetch_thread_context` for M2-018).
- Durable receipts/origins/outbound correlation unchanged.
- Tests with recorded fixtures; no SDK types in domain modules.

## Non-goals

- Treating Buzz threads as Holodeck workspaces.
- Auto-approving genesis or readiness from chat.

## Required invariants

- Collaboration system owns identity/conversation; Holodeck owns semantic work.
- Adapter failures must not invent trusted receipts.

## Acceptance criteria

- Authenticated Buzz intake maps to Holodeck actor + receipt + origin.
- Outbound status correlates to inbound receipt.
- Replay/idempotency holds.

## Verification

```text
uv run --extra dev pytest -q
```

## Evidence and handoff

Blocked pending explicit ungate.

## Residual risks

- Buzz API drift; revalidate against upstream before implementation.
