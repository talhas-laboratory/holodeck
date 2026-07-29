"""M2-018 conversation context preservation on task origins."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from holodeck_governance.adapters.collaboration import (
    InMemoryCollaborationAdapter,
    MemoryExternalActor,
)
from holodeck_governance.domain.collaboration import (
    ConversationContextManifestEntry,
    LocationKind,
    ProcessingOutcome,
    build_conversation_context_manifest,
)
from holodeck_governance.domain.collaboration.inbound import AttachmentRef
from holodeck_governance.domain.collaboration.origins import (
    conversation_context_manifest_from_jsonable,
    conversation_context_manifest_to_jsonable,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference

from test_m2_e2e_memory_intake import _payload, _world

TENANT = "01900000-0000-7000-8000-000000000001"
SYSTEM = "01900000-0000-7000-8000-000000000024"
ACTOR = "01900000-0000-7000-8000-000000000021"
NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def _attachment(external_id: str, locator: str) -> AttachmentRef:
    return AttachmentRef(
        attachment_id=generate_uuidv7(),
        external_attachment=ExternalReference(
            reference_id=generate_uuidv7(),
            tenant_id=TENANT,
            provider="memory",
            object_type="attachment",
            external_object_id=external_id,
            locator=locator,
            observed_at=NOW,
            created_at=NOW,
            created_by_actor_id=SYSTEM,
        ),
        content_type="text/plain",
    )


def test_build_manifest_orders_boundary_preceding_anchor_attachments() -> None:
    manifest = build_conversation_context_manifest(
        anchor_external_event_id="evt-anchor",
        anchor_locator="memory://events/evt-anchor",
        location_external_id="thread-1",
        location_locator="memory://threads/1",
        location_kind="thread",
        parent_location_external_id="channel-main",
        parent_location_locator="memory://channels/main",
        thread_entries=(
            ConversationContextManifestEntry(
                kind="message",
                external_id="msg-b",
                locator="memory://events/msg-b",
                relation="preceding",
                sequence=2,
            ),
            ConversationContextManifestEntry(
                kind="message",
                external_id="msg-a",
                locator="memory://events/msg-a",
                relation="preceding",
                sequence=1,
            ),
            ConversationContextManifestEntry(
                kind="omission",
                external_id="omission:truncated",
                relation="omission",
                note="history_truncated",
                sequence=0,
            ),
            ConversationContextManifestEntry(
                kind="message",
                external_id="evt-anchor",
                locator="memory://events/evt-anchor",
                relation="preceding",
                sequence=3,
            ),
        ),
        attachments=(_attachment("att-1", "memory://files/att-1"),),
    )
    relations = [entry.relation for entry in manifest]
    assert relations[:2] == ["thread_boundary", "parent_location"]
    assert [entry.external_id for entry in manifest if entry.relation == "preceding"] == [
        "msg-a",
        "msg-b",
    ]
    assert any(entry.relation == "omission" for entry in manifest)
    assert any(
        entry.relation == "anchor" and entry.external_id == "evt-anchor"
        for entry in manifest
    )
    assert any(
        entry.kind == "attachment" and entry.external_id == "att-1" for entry in manifest
    )
    assert [entry.sequence for entry in manifest] == list(range(len(manifest)))


def test_manifest_json_round_trip_preserves_enriched_fields() -> None:
    original = (
        ConversationContextManifestEntry(
            kind="message",
            external_id="msg-1",
            locator="memory://events/msg-1",
            relation="preceding",
            sequence=1,
            note="",
        ),
        ConversationContextManifestEntry(
            kind="omission",
            external_id="omission:partial",
            relation="omission",
            sequence=2,
            note="provider_page_limit",
        ),
    )
    restored = conversation_context_manifest_from_jsonable(
        conversation_context_manifest_to_jsonable(original)
    )
    assert restored == original


def test_legacy_manifest_json_defaults_relation() -> None:
    restored = conversation_context_manifest_from_jsonable(
        [
            {"kind": "message", "external_id": "msg-1", "locator": "x"},
            {"kind": "attachment", "external_id": "att-1"},
        ]
    )
    assert restored[0].relation == "preceding"
    assert restored[1].relation == "attachment"
    assert restored[0].sequence == 0


def test_invalid_manifest_kind_rejected() -> None:
    with pytest.raises(MalformedCommandError):
        ConversationContextManifestEntry(kind="tweet", external_id="x")


def test_memory_adapter_returns_seeded_ordered_preceding_context() -> None:
    adapter = InMemoryCollaborationAdapter(created_by_actor_id=SYSTEM)
    adapter.register_actor(
        MemoryExternalActor(
            external_actor_id="ext-owner",
            tenant_id=TENANT,
            actor_id=ACTOR,
            identity_locator="memory://actors/ext-owner",
        )
    )
    adapter.seed_thread_context(
        tenant_id=TENANT,
        location_kind=LocationKind.THREAD.value,
        external_location_id="thread-1",
        entries=(
            ConversationContextManifestEntry(
                kind="message",
                external_id="msg-2",
                locator="memory://events/msg-2",
                relation="preceding",
                sequence=2,
            ),
            ConversationContextManifestEntry(
                kind="message",
                external_id="msg-1",
                locator="memory://events/msg-1",
                relation="preceding",
                sequence=1,
            ),
            ConversationContextManifestEntry(
                kind="message",
                external_id="evt-anchor",
                locator="memory://events/evt-anchor",
                relation="preceding",
                sequence=3,
            ),
            ConversationContextManifestEntry(
                kind="omission",
                external_id="omission:older",
                relation="omission",
                note="older_than_window",
                sequence=0,
            ),
        ),
    )
    fetched = adapter.fetch_thread_context(
        tenant_id=TENANT,
        location_kind=LocationKind.THREAD.value,
        external_location_id="thread-1",
        anchor_external_event_id="evt-anchor",
    )
    assert [entry.external_id for entry in fetched] == [
        "omission:older",
        "msg-1",
        "msg-2",
    ]


def test_intake_persists_thread_history_and_attachments_on_origin() -> None:
    world = _world()
    world.adapter.seed_thread_context(
        tenant_id=world.ids.tenant_alpha,
        location_kind="channel",
        external_location_id="channel-main",
        entries=(
            ConversationContextManifestEntry(
                kind="message",
                external_id="msg-prior",
                locator="memory://events/msg-prior",
                relation="preceding",
                sequence=1,
            ),
            ConversationContextManifestEntry(
                kind="omission",
                external_id="omission:partial",
                relation="omission",
                note="provider_page_limit",
                sequence=0,
            ),
        ),
    )
    result = world.orchestrator.handle_inbound(
        _payload(
            world,
            external_event_id="evt-context-1",
            attachments=(
                {
                    "external_attachment_id": "att-notes",
                    "content_type": "text/plain",
                    "locator": "memory://files/att-notes",
                    "content_hash": "sha256:notes",
                },
            ),
        )
    )
    assert result.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
    assert result.origin is not None
    stored = world.service.get_task_origin(result.origin.object_id)
    assert stored is not None
    manifest = stored.conversation_context_manifest
    assert manifest
    assert manifest[0].relation == "thread_boundary"
    assert any(entry.relation == "parent_location" for entry in manifest)
    assert any(
        entry.external_id == "msg-prior" and entry.relation == "preceding"
        for entry in manifest
    )
    assert any(
        entry.relation == "anchor" and entry.external_id == "evt-context-1"
        for entry in manifest
    )
    assert any(
        entry.kind == "attachment" and entry.external_id == "att-notes"
        for entry in manifest
    )
    assert any(
        entry.kind == "omission" and entry.note == "provider_page_limit"
        for entry in manifest
    )


def test_intake_accepts_when_thread_fetch_fails() -> None:
    world = _world()
    world.adapter.mark_thread_context_unavailable(
        tenant_id=world.ids.tenant_alpha,
        location_kind="channel",
        external_location_id="channel-main",
    )
    result = world.orchestrator.handle_inbound(
        _payload(world, external_event_id="evt-context-fail")
    )
    assert result.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
    assert result.origin is not None
    manifest = result.origin.conversation_context_manifest
    assert any(
        entry.kind == "omission" and entry.note == "thread_context_unavailable"
        for entry in manifest
    )
    assert any(entry.relation == "anchor" for entry in manifest)


def test_intake_empty_thread_still_records_boundary_and_anchor() -> None:
    world = _world()
    result = world.orchestrator.handle_inbound(
        _payload(world, external_event_id="evt-context-empty")
    )
    assert result.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
    assert result.origin is not None
    relations = [entry.relation for entry in result.origin.conversation_context_manifest]
    assert relations[0] == "thread_boundary"
    assert "anchor" in relations
    assert "preceding" not in relations


def test_replay_preserves_persisted_conversation_context_manifest() -> None:
    world = _world()
    world.adapter.seed_thread_context(
        tenant_id=world.ids.tenant_alpha,
        location_kind="channel",
        external_location_id="channel-main",
        entries=(
            ConversationContextManifestEntry(
                kind="message",
                external_id="msg-prior",
                locator="memory://events/msg-prior",
                relation="preceding",
                sequence=1,
            ),
        ),
    )
    payload = _payload(world, external_event_id="evt-context-replay")
    first = world.orchestrator.handle_inbound(payload)
    assert first.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
    assert first.origin is not None
    first_manifest = first.origin.conversation_context_manifest

    # Clear seed so a naive re-fetch would lose history; replay must use origin.
    world.adapter._thread_history.clear()
    replay = world.orchestrator.handle_inbound(payload)
    assert replay.processing_outcome is ProcessingOutcome.DUPLICATE_REPLAY
    assert replay.origin is not None
    assert replay.origin.conversation_context_manifest == first_manifest
    stored = world.service.get_task_origin(first.origin.object_id)
    assert stored is not None
    assert stored.conversation_context_manifest == first_manifest
