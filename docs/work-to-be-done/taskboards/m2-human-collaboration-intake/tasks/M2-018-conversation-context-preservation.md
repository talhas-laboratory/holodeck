# M2-018 — Conversation context preservation

**Status:** ready
**Owner:** unassigned
**Depends on:** M2-003, M2-008

## Outcome

Preserve enough originating conversation context on task origins (message and
attachment references) for later reconstitution, without treating the
collaboration thread as the Holodeck system of record.

## In scope

- Optional `conversation_context_manifest` on `TaskOrigin` (tuple of message /
  attachment refs) persisted as JSON.
- `CollaborationAdapter.fetch_thread_context` protocol method + memory adapter
  stub returning empty/fixture context.
- Tests for persistence round-trip and adapter stub.

## Non-goals

- Full Buzz thread sync (M2-009).
- Using conversation text as mission authority.

## Required invariants

- Manifest refs are opaque external references / adapter ids, not Holodeck
  workspace ids.
- Missing context must not block intake acceptance.

## Acceptance criteria

- Origins can persist and reload a conversation context manifest.
- Memory adapter exposes `fetch_thread_context` returning a stable empty or
  fixture payload.
- Application remains free of provider SDK types.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_task_origins.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Minimal domain+persistence stub landed with acceptance-blocker fixes:

- `ConversationContextManifestEntry` + optional
  `TaskOrigin.conversation_context_manifest` persisted as JSON (migration v21
  column).
- `CollaborationAdapter.fetch_thread_context` + memory adapter empty stub.
- Tests: origin round-trip + memory stub.

Full Buzz-backed fetch remains M2-009. Leave status **ready** until a fuller
intake wiring slice lands.

## Residual risks

- Provider thread APIs vary; keep the port intentionally thin.
