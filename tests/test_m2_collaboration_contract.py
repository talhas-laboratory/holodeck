"""M2-001 provider-neutral collaboration contract suite."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from holodeck_governance.domain.collaboration import (
    ADAPTER_METADATA_FIELD,
    CIS_EXPECTATIONS,
    INTAKE_VERB_WORK,
    M2_COMMAND_ORIGIN_RECORD,
    M2_COMMAND_OUTBOUND_ENQUEUE,
    M2_COMMAND_RECEIPT_RECORD,
    STABLE_INBOUND_FIELDS,
    AttachmentRef,
    CollaborationAdapter,
    ConversationLocation,
    InboundEventReceipt,
    IntakePolicyInputs,
    LocationKind,
    NormalizedInboundEvent,
    OutboundCollaborationMessage,
    ProcessingOutcome,
    VerificationResult,
    VerifiedActorIdentity,
    inbound_receipt_dedupe_key,
    outbound_idempotency_key,
    parse_intake_command,
    required_scenario_ids,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.provenance.external_reference import ExternalReference

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "plans" / "2026-07-27-m2-collaboration-intake-design.md"
TEST_SPEC = (
    ROOT / "docs" / "plans" / "2026-07-27-m2-collaboration-intake-test-specification.md"
)
COLLAB_DOMAIN = ROOT / "src" / "holodeck_governance" / "domain" / "collaboration"

TENANT = "00000000-0000-7000-8000-0000000000a1"
ACTOR = "00000000-0000-7000-8000-0000000000a2"
INBOUND = "00000000-0000-7000-8000-0000000000b1"
RECEIPT = "00000000-0000-7000-8000-0000000000b2"
SOURCE_REF = "00000000-0000-7000-8000-0000000000b3"
IDENTITY_REF = "00000000-0000-7000-8000-0000000000b4"
LOCATION_REF = "00000000-0000-7000-8000-0000000000b5"
ATTACHMENT = "00000000-0000-7000-8000-0000000000b6"
ATTACHMENT_REF = "00000000-0000-7000-8000-0000000000b7"
ORIGIN = "00000000-0000-7000-8000-0000000000c1"
MESSAGE = "00000000-0000-7000-8000-0000000000c2"
COMMAND = "00000000-0000-7000-8000-0000000000c3"
CHECKPOINT = "00000000-0000-7000-8000-0000000000c4"
NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def _ext(
    reference_id: str,
    *,
    object_type: str,
    external_object_id: str,
    locator: str,
) -> ExternalReference:
    return ExternalReference(
        reference_id=reference_id,
        tenant_id=TENANT,
        provider="memory",
        object_type=object_type,
        external_object_id=external_object_id,
        locator=locator,
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ACTOR,
    )


def _actor() -> VerifiedActorIdentity:
    return VerifiedActorIdentity(
        tenant_id=TENANT,
        actor_id=ACTOR,
        external_identity=_ext(
            IDENTITY_REF,
            object_type="actor_identity",
            external_object_id="ext-actor-1",
            locator="memory://actors/ext-actor-1",
        ),
        verification_result=VerificationResult.VERIFIED,
        verified_at=NOW,
        adapter_metadata={"npub_display": "adapter-only"},
    )


def _location() -> ConversationLocation:
    return ConversationLocation(
        location_kind=LocationKind.THREAD,
        external_location=_ext(
            LOCATION_REF,
            object_type="conversation_thread",
            external_object_id="thread-1",
            locator="memory://channels/main/threads/1",
        ),
        adapter_metadata={"display_path": "#main / thread 1"},
    )


def _event(body: str = "@holodeck work: fix flaky claim race") -> NormalizedInboundEvent:
    return NormalizedInboundEvent(
        inbound_event_id=INBOUND,
        tenant_id=TENANT,
        provider="memory",
        external_event_id="evt-1",
        occurred_at=NOW,
        received_at=NOW,
        verified_actor=_actor(),
        location=_location(),
        body_text=body,
        source_reference=_ext(
            SOURCE_REF,
            object_type="collaboration_event",
            external_object_id="evt-1",
            locator="memory://events/evt-1",
        ),
        attachments=(
            AttachmentRef(
                attachment_id=ATTACHMENT,
                external_attachment=_ext(
                    ATTACHMENT_REF,
                    object_type="attachment",
                    external_object_id="file-1",
                    locator="memory://files/file-1",
                ),
                content_type="text/plain",
                content_hash="sha256:demo",
                byte_size=12,
                adapter_metadata={"filename": "notes.txt"},
            ),
        ),
        adapter_metadata={"relay_request_id": "rr-1"},
    )


def test_design_and_test_specification_exist() -> None:
    assert DESIGN.is_file()
    assert TEST_SPEC.is_file()
    design = DESIGN.read_text(encoding="utf-8")
    spec = TEST_SPEC.read_text(encoding="utf-8")
    assert "Stable Holodeck data versus adapter metadata" in design
    assert "CIS-001" in spec and "CIS-008" in spec
    assert M2_COMMAND_RECEIPT_RECORD in design
    assert M2_COMMAND_ORIGIN_RECORD in design
    assert M2_COMMAND_OUTBOUND_ENQUEUE in design


def test_scenario_catalog_is_complete_and_self_consistent() -> None:
    assert set(CIS_EXPECTATIONS) == set(required_scenario_ids())
    for scenario_id, expectation in CIS_EXPECTATIONS.items():
        assert expectation.scenario_id == scenario_id
        if expectation.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN:
            assert "task_origin" in expectation.expected_records
            assert expectation.expected_outbox_actions
            assert "mission" in expectation.absent_writes
            assert "approval" in expectation.absent_writes
            assert "acceptance" in expectation.absent_writes
        if expectation.processing_outcome in {
            ProcessingOutcome.REJECTED,
            ProcessingOutcome.IGNORED_NON_INTAKE,
            ProcessingOutcome.AUTH_FAILED,
        }:
            assert "task_origin" in expectation.absent_writes
            assert any(
                item.startswith("success_outbox_item")
                for item in expectation.absent_writes
            )


def test_stable_fields_versus_adapter_metadata_partition() -> None:
    assert ADAPTER_METADATA_FIELD == "adapter_metadata"
    assert "adapter_metadata" not in STABLE_INBOUND_FIELDS
    assert {
        "inbound_event_id",
        "tenant_id",
        "provider",
        "external_event_id",
        "body_text",
        "source_reference",
    } <= STABLE_INBOUND_FIELDS
    event = _event()
    assert "relay_request_id" in event.adapter_metadata
    assert event.verified_actor.adapter_metadata["npub_display"] == "adapter-only"
    assert event.location.adapter_metadata["display_path"].startswith("#main")


@pytest.mark.parametrize(
    ("text", "explicit", "subject"),
    [
        ("@holodeck work: fix flaky claim race", True, "fix flaky claim race"),
        ("@Holodeck work fix flaky claim race", True, "fix flaky claim race"),
        ("/holodeck work: ship docs", True, "ship docs"),
        ("please review the PR", False, None),
        ("@holodeck status: where are we?", False, "where are we?"),
        ("@holodeck work:", False, ""),
        ("@holodeck work", False, ""),
    ],
)
def test_intake_grammar(text: str, explicit: bool, subject: str | None) -> None:
    command = parse_intake_command(text)
    assert command.is_explicit_intake is explicit
    if explicit:
        assert command.verb == INTAKE_VERB_WORK
        assert command.subject_text == subject
    else:
        assert command.subject_text == subject


def test_receipt_dedupe_and_accepted_origin_invariant() -> None:
    receipt = InboundEventReceipt(
        receipt_id=RECEIPT,
        tenant_id=TENANT,
        provider="memory",
        external_event_id="evt-1",
        inbound_event_id=INBOUND,
        signed_source_reference_id=SOURCE_REF,
        verification_result=VerificationResult.VERIFIED,
        processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
        reason_codes=("reason.allowed",),
        checkpoint_token=CHECKPOINT,
        created_at=NOW,
        command_id=COMMAND,
        task_origin_object_id=ORIGIN,
    )
    assert inbound_receipt_dedupe_key(receipt) == (TENANT, "memory", "evt-1")
    with pytest.raises(MalformedCommandError):
        InboundEventReceipt(
            receipt_id=RECEIPT,
            tenant_id=TENANT,
            provider="memory",
            external_event_id="evt-1",
            inbound_event_id=INBOUND,
            signed_source_reference_id=SOURCE_REF,
            verification_result=VerificationResult.VERIFIED,
            processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
            reason_codes=("reason.allowed",),
            checkpoint_token=CHECKPOINT,
            created_at=NOW,
        )


def test_outbound_correlation_and_idempotency_key() -> None:
    key = outbound_idempotency_key(
        tenant_id=TENANT,
        provider="memory",
        task_origin_object_id=ORIGIN,
        status_kind="accepted",
    )
    message = OutboundCollaborationMessage(
        message_id=MESSAGE,
        tenant_id=TENANT,
        provider="memory",
        destination=_location(),
        body_text="Holodeck recorded task origin " + ORIGIN,
        task_origin_object_id=ORIGIN,
        inbound_receipt_id=RECEIPT,
        command_id=COMMAND,
        idempotency_key=key,
        created_at=NOW,
    )
    assert message.inbound_receipt_id == RECEIPT
    assert message.task_origin_object_id == ORIGIN
    assert key == f"{TENANT}:memory:status:{ORIGIN}:accepted"


def test_policy_inputs_and_m1_command_mapping_constants() -> None:
    policy = IntakePolicyInputs(
        tenant_id=TENANT,
        actor_id=ACTOR,
        location=_location(),
    )
    assert policy.required_capability == "collaboration.intake"
    assert M2_COMMAND_RECEIPT_RECORD == "collaboration.receipt.record"
    assert M2_COMMAND_ORIGIN_RECORD == "collaboration.origin.record"
    assert M2_COMMAND_OUTBOUND_ENQUEUE == "collaboration.outbound.enqueue"
    for expectation in CIS_EXPECTATIONS.values():
        for command_type in expectation.m1_command_types:
            assert command_type.startswith("collaboration.")


def test_collaboration_adapter_protocol_shape() -> None:
    class MemoryAdapter:
        def normalize_inbound(self, raw_provider_payload):  # type: ignore[no-untyped-def]
            return _event(str(raw_provider_payload.get("text", "")))

        def verify_and_map_actor(self, event):  # type: ignore[no-untyped-def]
            return event.verified_actor

        def publish_outbound(self, message):  # type: ignore[no-untyped-def]
            return {"ack": "local", "idempotency_key": message.idempotency_key}

    adapter: CollaborationAdapter = MemoryAdapter()
    event = adapter.normalize_inbound({"text": "@holodeck work: demo"})
    assert event.provider == "memory"
    assert (
        adapter.verify_and_map_actor(event).verification_result
        is VerificationResult.VERIFIED
    )
    assert "ack" in adapter.publish_outbound(
        OutboundCollaborationMessage(
            message_id=MESSAGE,
            tenant_id=TENANT,
            provider="memory",
            destination=_location(),
            body_text="ok",
            task_origin_object_id=ORIGIN,
            inbound_receipt_id=RECEIPT,
            command_id=COMMAND,
            idempotency_key="k",
            created_at=NOW,
        )
    )


def test_domain_collaboration_package_forbids_provider_and_storage_imports() -> None:
    forbidden_prefixes = (
        "sqlite3",
        "http",
        "urllib",
        "mcp",
        "buzz",
        "nostr",
        "slack_sdk",
        "holodeck_governance.storage",
        "holodeck_governance.application",
        "holodeck_control_plane",
    )
    for path in sorted(COLLAB_DOMAIN.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                assert not any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in forbidden_prefixes
                ), f"{path} imports forbidden module {name}"
