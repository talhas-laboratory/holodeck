# Decisions

## 2026-07-24 — M1 governance kernel

- The kernel is adapter-agnostic and governance-strict.
- Use typed relational current state plus an append-only event/audit ledger.
- Use default-local tenant support now; enforce tenant isolation.
- Use UUIDv7-style opaque IDs, stable object IDs, and immutable sequential revisions.
- Use direct ownership foreign keys plus typed/versioned traceability edges.
- Make commands the sole mutation path and retain every command receipt.
- Use explicit code-defined evaluators and typed governance primitives; policy
  supplies parameters only. No free-form evaluator DSL or generic `not`.
- Bind authority grants and approvals to exact subject revisions; grants are
  expiring and separately revocable.
- Evaluate immutable snapshots and fail closed on incomplete or stale inputs.
- Commit receipt, evaluation, permitted transition, event, and outbox atomically.
- Use at-least-once outbox delivery with leases, backoff, dead letters, and
  escalation.
- Treat existing runtime records as additive `legacy_import` data; never invent
  historic M1 authority or evidence.

## 2026-07-24 — Executable governance scenarios precede implementation

- M1-002 defines primitive, evaluator-contract, and full governance scenarios
  before persistence and command work begins.
- Downstream implementation packets must trace their test plans to scenario IDs.
- A rejection scenario asserts both the durable audit result and the absence of
  unauthorized state, success event, and success outbox effects.

## 2026-07-24 — Atomic implementation packets

- Replace broad subsystem workstreams with initially 25 dependency-ordered packets.
- Each implementation packet owns one narrow contract or behavior, declares
  scenario IDs, and has one observable verification target.
- M1-024 is the only whole-system proof packet; M1-025 publishes the verified
  contract and M2 handoff.

See the linked design for the complete rationale and acceptance boundary.

## 2026-07-24 — Fresh-builder completeness repair

- The full typed work vocabulary is implemented by explicit record-family packets;
  it is not implicit in revisions, edges, or later scenario fixtures.
- Repository interfaces and the unit-of-work transaction boundary are a dedicated
  M1 deliverable. The boundary owns atomic receipt, evaluation, transition,
  event, and outbox persistence.
- A versioned domain-error/reason-code catalog and event-schema catalog are
  explicit M1 contracts. Tests refer to catalog identifiers, not prose-only
  explanations.
- The existing dirty worktree and governed-mission thin slice are migration
  inputs, not a presumed accepted baseline. `BUILDER_BASELINE.md` defines the
  reproducible starting point and must be refreshed before implementation.
- UUIDv7, legacy lifecycle mapping, and SQLite typed-edge enforcement are
  implementation decisions with named owners and acceptance tests; no builder
  may silently choose incompatible behavior.
