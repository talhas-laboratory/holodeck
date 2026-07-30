# M2-018 — Conversation context preservation

**Status:** done
**Owner:** cursor
**Depends on:** M2-003, M2-008

## Outcome

Preserve enough originating conversation context on task origins (message and
attachment references) for later reconstitution, without treating the
collaboration thread as the Holodeck system of record.

## In scope

- Optional `conversation_context_manifest` on `TaskOrigin` (tuple of message /
  attachment / omission refs) persisted as JSON.
- Enriched manifest entries: `relation` (anchor, preceding, attachment,
  thread_boundary, parent_location, omission), deterministic `sequence`, and
  optional `note`.
- Domain `build_conversation_context_manifest` merge helper.
- `CollaborationAdapter.fetch_thread_context` + memory adapter seeded history /
  partial-omission / fail-open harness behavior.
- Intake wiring: fetch thread context, merge event attachments, persist with
  origin commit; missing context does not block acceptance.

## Non-goals

- Full Buzz thread sync (M2-009).
- Using conversation text as mission authority.

## Required invariants

- Manifest refs are opaque external references / adapter ids, not Holodeck
  workspace ids.
- Missing context must not block intake acceptance.
- Replay returns the persisted origin manifest (not a re-fetch).

## Acceptance criteria

- Origins can persist and reload a conversation context manifest.
- Memory adapter exposes `fetch_thread_context` returning empty, seeded
  preceding history, or partial omission entries.
- Intake stores boundary + preceding + anchor + attachments (+ omissions).
- Application remains free of provider SDK types.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_conversation_context.py
uv run --extra dev pytest -q tests/test_m2_018_messy_slack_thread_fixture.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Full capture workflow landed on `cursor/m2-018-conversation-context-preservation-2175`:

- Enriched `ConversationContextManifestEntry` + `build_conversation_context_manifest`.
- Intake `_capture_conversation_context` calls `fetch_thread_context` fail-open
  and commits the manifest with `accept_task_origin_with_outbound`.
- Memory harness: `seed_thread_context`, `mark_thread_context_unavailable`,
  ordered preceding fetch excluding anchor.
- Tests: domain ordering/JSON, adapter seed/partial, intake E2E with
  attachments, empty/fail-open, replay preservation
  (`tests/test_m2_conversation_context.py`).
- Slack-shaped messy thread acceptance fixture
  (`tests/test_m2_018_messy_slack_thread_fixture.py`): noisy channel+thread
  with truncated history and attachments; asserts full ordered manifest
  capture, explicitly not semantic selection.

Full Buzz-backed fetch remains M2-009.

## Residual risks

- Provider thread APIs vary; keep the port intentionally thin.
- Buzz live history retrieval still gated on M2-009.
