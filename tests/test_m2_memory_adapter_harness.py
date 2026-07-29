"""M2-008 provider-neutral in-memory collaboration adapter harness."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from holodeck_governance.adapters.collaboration import (
    MEMORY_PROVIDER,
    CollaborationAdapterAuthError,
    InMemoryCollaborationAdapter,
    MemoryExternalActor,
)
from holodeck_governance.domain.collaboration import (
    CollaborationAdapter,
    LocationKind,
    OutboundCollaborationMessage,
    VerificationResult,
    parse_intake_command,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import generate_uuidv7

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_COLLAB = ROOT / "src" / "holodeck_governance" / "domain" / "collaboration"
ADAPTERS_ROOT = ROOT / "src" / "holodeck_governance" / "adapters"

TENANT = "01900000-0000-7000-8000-000000000001"
ACTOR = "01900000-0000-7000-8000-000000000021"
SYSTEM = "01900000-0000-7000-8000-000000000024"
ORIGIN = "01900000-0000-7000-8000-000000000031"
RECEIPT = "01900000-0000-7000-8000-000000000032"
COMMAND = "01900000-0000-7000-8000-000000000033"
MESSAGE = "01900000-0000-7000-8000-000000000034"
NOW = datetime(2026, 7, 29, 11, 0, tzinfo=UTC)


def _adapter() -> InMemoryCollaborationAdapter:
    adapter = InMemoryCollaborationAdapter(
        created_by_actor_id=SYSTEM,
        clock=lambda: NOW,
        id_factory=generate_uuidv7,
    )
    adapter.register_actor(
        MemoryExternalActor(
            external_actor_id="ext-owner",
            tenant_id=TENANT,
            actor_id=ACTOR,
            identity_locator="memory://actors/ext-owner",
            display_name="Owner",
        )
    )
    return adapter


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "tenant_id": TENANT,
        "external_event_id": "evt-1",
        "external_actor_id": "ext-owner",
        "body_text": "@holodeck work: ship memory harness",
        "location_kind": "channel",
        "external_location_id": "channel-main",
        "location_locator": "memory://channels/main",
        "parent_location_kind": "community",
        "parent_external_location_id": "community-alpha",
        "signature": "ok",
        "occurred_at": NOW.isoformat(),
        "endpoint_id": "01900000-0000-7000-8000-000000000040",
    }
    base.update(overrides)
    return base


def test_adapter_satisfies_collaboration_adapter_protocol() -> None:
    adapter: CollaborationAdapter = _adapter()
    event = adapter.normalize_inbound(_payload())
    assert event.provider == MEMORY_PROVIDER
    verified = adapter.verify_and_map_actor(event)
    assert verified.verification_result is VerificationResult.VERIFIED
    assert verified.actor_id == ACTOR


def test_normalize_verified_intake_event() -> None:
    adapter = _adapter()
    event = adapter.normalize_inbound(_payload())
    assert event.tenant_id == TENANT
    assert event.external_event_id == "evt-1"
    assert event.body_text.startswith("@holodeck work:")
    assert event.location.location_kind is LocationKind.CHANNEL
    assert event.location.parent_external_location is not None
    assert event.location.endpoint_id is not None
    assert event.verified_actor.verification_result is VerificationResult.VERIFIED
    assert event.source_reference.provider == MEMORY_PROVIDER
    intake = parse_intake_command(event.body_text)
    assert intake.is_explicit_intake
    assert intake.subject_text == "ship memory harness"


def test_unsigned_and_invalid_signature_refuse_normalization() -> None:
    adapter = _adapter()
    with pytest.raises(CollaborationAdapterAuthError) as unsigned:
        adapter.normalize_inbound(_payload(signature=""))
    assert unsigned.value.verification_result is VerificationResult.UNSIGNED

    with pytest.raises(CollaborationAdapterAuthError) as failed:
        adapter.normalize_inbound(_payload(signature="bad"))
    assert failed.value.verification_result is VerificationResult.FAILED


def test_unknown_external_actor_refuses_normalization() -> None:
    adapter = _adapter()
    with pytest.raises(CollaborationAdapterAuthError) as err:
        adapter.normalize_inbound(_payload(external_actor_id="nobody"))
    assert err.value.verification_result is VerificationResult.FAILED


def test_publish_outbound_is_idempotent() -> None:
    adapter = _adapter()
    event = adapter.normalize_inbound(_payload())
    message = OutboundCollaborationMessage(
        message_id=MESSAGE,
        tenant_id=TENANT,
        provider=MEMORY_PROVIDER,
        destination=event.location,
        body_text="accepted",
        task_origin_object_id=ORIGIN,
        inbound_receipt_id=RECEIPT,
        command_id=COMMAND,
        idempotency_key=f"{TENANT}:memory:status:{ORIGIN}:accepted",
        created_at=NOW,
    )
    first = adapter.publish_outbound(message)
    second = adapter.publish_outbound(message)
    assert first == second
    assert first["status"] == "delivered"
    assert first["idempotency_key"] == message.idempotency_key
    assert len(adapter.published_messages) == 1
    assert adapter.published_messages[0].message_id == MESSAGE


def test_publish_rejects_non_memory_provider() -> None:
    adapter = _adapter()
    event = adapter.normalize_inbound(_payload())
    with pytest.raises(MalformedCommandError):
        adapter.publish_outbound(
            OutboundCollaborationMessage(
                message_id=MESSAGE,
                tenant_id=TENANT,
                provider="buzz",
                destination=event.location,
                body_text="nope",
                task_origin_object_id=ORIGIN,
                inbound_receipt_id=RECEIPT,
                command_id=COMMAND,
                idempotency_key="k",
                created_at=NOW,
            )
        )


def test_domain_collaboration_does_not_import_adapters() -> None:
    violations: list[str] = []
    for path in DOMAIN_COLLAB.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name == "holodeck_governance.adapters" or name.startswith(
                    "holodeck_governance.adapters."
                ):
                    violations.append(f"{path.name} imports {name}")
    assert violations == []


def test_adapters_package_exists_outside_domain() -> None:
    assert (ADAPTERS_ROOT / "collaboration" / "memory.py").is_file()
    assert not (DOMAIN_COLLAB / "memory.py").exists()


def test_memory_adapter_fetch_thread_context_stub() -> None:
    adapter = _adapter()
    assert adapter.fetch_thread_context(
        tenant_id=TENANT,
        location_kind=LocationKind.THREAD.value,
        external_location_id="thread-1",
    ) == ()
