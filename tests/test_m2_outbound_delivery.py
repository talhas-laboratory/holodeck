"""M2-004 transactional outbound collaboration-message delivery."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.assignments import RoleAssignment
from holodeck_governance.domain.authority.roles import RoleProfile
from holodeck_governance.domain.catalogs.events import EventType
from holodeck_governance.domain.collaboration import (
    BindingStatus,
    CollaborationEndpoint,
    ConversationLocation,
    ExternalActorMapping,
    InboundEventReceipt,
    LocationKind,
    OutboundCollaborationMessage,
    ProcessingOutcome,
    TaskOrigin,
    VerificationResult,
    outbound_idempotency_key,
)
from holodeck_governance.domain.errors import (
    MalformedCommandError,
    NotFoundGovernanceError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.collaboration import (
    COLLABORATION_STATUS_DELIVERY_PURPOSE,
    SqliteCollaborationRepository,
)
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
)
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 27, 16, 30, tzinfo=UTC)


def _service() -> tuple[sqlite3.Connection, CollaborationApplicationService, FixtureIds]:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_governance(conn)
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    auth = SqliteAuthorityRepository(conn)
    auth.save_actor(
        Actor(
            actor_id=ids.human_owner,
            tenant_id=ids.tenant_alpha,
            kind=ActorKind.HUMAN,
            display_name="Owner",
            created_at=FIXED_CLOCK,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_actor(
        Actor(
            actor_id=ids.system_service,
            tenant_id=ids.tenant_alpha,
            kind=ActorKind.SERVICE,
            display_name="System",
            created_at=FIXED_CLOCK,
            created_by_actor_id=ids.system_service,
        )
    )
    _grant_intake_authority(conn, ids, actor_id=ids.human_owner)
    service = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )
    return conn, service, ids


def _grant_intake_authority(
    conn: sqlite3.Connection, ids: FixtureIds, *, actor_id: str
) -> None:
    auth = SqliteAuthorityRepository(conn)
    revisions = SqliteRevisionRepository(conn)
    role_object_id = generate_uuidv7()
    revisions.register_object(
        GovernanceObject(
            object_id=role_object_id,
            tenant_id=ids.tenant_alpha,
            object_type="RoleProfile",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_role_profile(
        RoleProfile(
            role_profile_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            role_object_id=role_object_id,
            revision=1,
            name="collaborator",
            permissions=("collaboration.intake",),
            jurisdiction={"tenant": ids.tenant_alpha},
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_assignment(
        RoleAssignment(
            assignment_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            actor_id=actor_id,
            role_object_id=role_object_id,
            role_revision=1,
            workspace_object_id=None,
            jurisdiction_key="tenant",
            jurisdiction_value=ids.tenant_alpha,
            effective_from=NOW - timedelta(hours=1),
            created_at=NOW,
            created_by_actor_id=ids.system_service,
            effective_until=NOW + timedelta(days=30),
        )
    )


def _ref(
    ids: FixtureIds,
    *,
    object_type: str,
    external_object_id: str,
    locator: str,
) -> ExternalReference:
    return ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        object_type=object_type,
        external_object_id=external_object_id,
        locator=locator,
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )


def _accepted_origin(
    service: CollaborationApplicationService, ids: FixtureIds
) -> tuple[CollaborationEndpoint, TaskOrigin, InboundEventReceipt, ExternalReference]:
    endpoint = CollaborationEndpoint(
        endpoint_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        external_endpoint_id="community-alpha",
        locator="memory://community-alpha",
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_endpoint(endpoint)
    identity = _ref(
        ids,
        object_type="actor_identity",
        external_object_id="ext-owner",
        locator="memory://actors/owner",
    )
    service.save_external_reference(identity)
    mapping = ExternalActorMapping(
        mapping_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        endpoint_id=endpoint.endpoint_id,
        actor_id=ids.human_owner,
        provider="memory",
        external_actor_id=identity.external_object_id,
        external_identity_reference_id=identity.reference_id,
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_actor_mapping(mapping)
    source = _ref(
        ids,
        object_type="collaboration_event",
        external_object_id="evt-out-1",
        locator="memory://events/evt-out-1",
    )
    location = _ref(
        ids,
        object_type="conversation_thread",
        external_object_id="thread-1",
        locator="memory://channels/main/threads/1",
    )
    parent = _ref(
        ids,
        object_type="conversation_channel",
        external_object_id="channel-main",
        locator="memory://channels/main",
    )
    origin_id = generate_uuidv7()
    receipt_id = generate_uuidv7()
    receipt = InboundEventReceipt(
        receipt_id=receipt_id,
        tenant_id=ids.tenant_alpha,
        provider="memory",
        external_event_id="evt-out-1",
        inbound_event_id=generate_uuidv7(),
        signed_source_reference_id=source.reference_id,
        verification_result=VerificationResult.VERIFIED,
        processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
        reason_codes=("reason.allowed",),
        checkpoint_token=generate_uuidv7(),
        created_at=NOW,
        task_origin_object_id=origin_id,
        mapping_id=mapping.mapping_id,
        external_actor_id=mapping.external_actor_id,
    )
    origin = TaskOrigin(
        object_id=origin_id,
        tenant_id=ids.tenant_alpha,
        actor_id=ids.human_owner,
        inbound_receipt_id=receipt_id,
        source_reference_id=source.reference_id,
        provider="memory",
        external_event_id="evt-out-1",
        subject_text="ship correlated status",
        body_text="@holodeck work: ship correlated status",
        location_kind=LocationKind.THREAD,
        location_reference_id=location.reference_id,
        parent_location_reference_id=parent.reference_id,
        endpoint_id=endpoint.endpoint_id,
        mapping_id=mapping.mapping_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    result = service.accept_task_origin(
        origin=origin,
        receipt=receipt,
        source_reference=source,
        location_reference=location,
        parent_location_reference=parent,
        endpoint_id=endpoint.endpoint_id,
    )
    assert result.created is True
    return endpoint, result.origin, result.receipt, location


def _status_message(
    ids: FixtureIds,
    *,
    origin: TaskOrigin,
    receipt: InboundEventReceipt,
    location: ExternalReference,
    endpoint_id: str,
    status_kind: str = "accepted",
) -> OutboundCollaborationMessage:
    key = outbound_idempotency_key(
        tenant_id=ids.tenant_alpha,
        provider="memory",
        task_origin_object_id=origin.object_id,
        status_kind=status_kind,
    )
    return OutboundCollaborationMessage(
        message_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        destination=ConversationLocation(
            location_kind=LocationKind.THREAD,
            external_location=location,
            endpoint_id=endpoint_id,
        ),
        body_text=f"Holodeck recorded task origin {origin.object_id}",
        task_origin_object_id=origin.object_id,
        inbound_receipt_id=receipt.receipt_id,
        command_id=generate_uuidv7(),
        idempotency_key=key,
        created_at=NOW,
    )


def test_migrate_v15_creates_outbound_messages_table() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    assert governance_schema_version(conn) == 17
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "gov_outbound_collaboration_messages" in tables


def test_enqueue_outbound_status_correlates_cis007() -> None:
    conn, service, ids = _service()
    endpoint, origin, receipt, location = _accepted_origin(service, ids)
    message = _status_message(
        ids,
        origin=origin,
        receipt=receipt,
        location=location,
        endpoint_id=endpoint.endpoint_id,
    )
    result = service.enqueue_outbound_status(message)
    assert result.created is True
    assert result.message.task_origin_object_id == origin.object_id
    assert result.message.inbound_receipt_id == receipt.receipt_id
    assert result.outbox_item_id
    loaded = service.get_outbound_message(message.message_id)
    assert loaded == result.message

    outbox = conn.execute(
        "SELECT * FROM gov_outbox_items WHERE outbox_item_id = ?",
        (result.outbox_item_id,),
    ).fetchone()
    assert outbox is not None
    assert str(outbox["status"]) == "pending"
    assert str(outbox["dedup_key"]) == message.idempotency_key
    assert str(outbox["delivery_purpose"]) == COLLABORATION_STATUS_DELIVERY_PURPOSE
    assert str(outbox["tenant_id"]) == ids.tenant_alpha

    event = conn.execute(
        """
        SELECT event_type FROM gov_domain_events
        WHERE event_id = (
            SELECT domain_event_id FROM gov_outbound_collaboration_messages
            WHERE message_id = ?
        )
        """,
        (message.message_id,),
    ).fetchone()
    assert str(event["event_type"]) == EventType.OUTBOX_ENQUEUED.value
    assert conn.execute("SELECT COUNT(*) FROM gov_missions").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_runs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_approvals").fetchone()[0] == 0


def test_duplicate_outbound_enqueue_replays_same_outbox_item() -> None:
    conn, service, ids = _service()
    endpoint, origin, receipt, location = _accepted_origin(service, ids)
    first_message = _status_message(
        ids,
        origin=origin,
        receipt=receipt,
        location=location,
        endpoint_id=endpoint.endpoint_id,
    )
    first = service.enqueue_outbound_status(first_message)
    retry = OutboundCollaborationMessage(
        message_id=generate_uuidv7(),
        tenant_id=first_message.tenant_id,
        provider=first_message.provider,
        destination=first_message.destination,
        body_text="different body ignored on replay",
        task_origin_object_id=origin.object_id,
        inbound_receipt_id=receipt.receipt_id,
        command_id=generate_uuidv7(),
        idempotency_key=first_message.idempotency_key,
        created_at=NOW,
    )
    second = service.enqueue_outbound_status(retry)
    assert first.created is True
    assert second.created is False
    assert second.message.message_id == first.message.message_id
    assert second.outbox_item_id == first.outbox_item_id
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_outbound_collaboration_messages"
        ).fetchone()[0]
        == 1
    )
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 1


def test_uncorrelated_outbound_receipt_rejected() -> None:
    _conn, service, ids = _service()
    endpoint, origin, receipt, location = _accepted_origin(service, ids)
    message = _status_message(
        ids,
        origin=origin,
        receipt=receipt,
        location=location,
        endpoint_id=endpoint.endpoint_id,
    )
    bad = OutboundCollaborationMessage(
        message_id=message.message_id,
        tenant_id=message.tenant_id,
        provider=message.provider,
        destination=message.destination,
        body_text=message.body_text,
        task_origin_object_id=origin.object_id,
        inbound_receipt_id=generate_uuidv7(),
        command_id=message.command_id,
        idempotency_key=message.idempotency_key,
        created_at=NOW,
    )
    with pytest.raises((MalformedCommandError, NotFoundGovernanceError)):
        service.enqueue_outbound_status(bad)
