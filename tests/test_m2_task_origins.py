"""M2-003 durable task origins and source-thread context."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.assignments import RoleAssignment
from holodeck_governance.domain.authority.roles import RoleProfile
from holodeck_governance.domain.collaboration import (
    BindingStatus,
    CollaborationEndpoint,
    ExternalActorMapping,
    InboundEventReceipt,
    LocationKind,
    ProcessingOutcome,
    TaskOrigin,
    VerificationResult,
)
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    MalformedCommandError,
    MissingAuthorityError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.collaboration import SqliteCollaborationRepository
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
)
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 27, 14, 0, tzinfo=UTC)


def _service() -> tuple[sqlite3.Connection, CollaborationApplicationService, FixtureIds]:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_governance(conn)
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'beta', 'Beta', 'm1.tenant.v1', ?, ?, NULL, 'active', 0)
        """,
        (ids.tenant_beta, NOW.isoformat(), ids.system_service),
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
    auth.save_actor(
        Actor(
            actor_id=ids.human_reviewer,
            tenant_id=ids.tenant_beta,
            kind=ActorKind.HUMAN,
            display_name="Beta human",
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


def _endpoint(ids: FixtureIds) -> CollaborationEndpoint:
    return CollaborationEndpoint(
        endpoint_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        external_endpoint_id="community-alpha",
        locator="memory://community-alpha",
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
        display_name="Alpha",
    )


def _bind_actor(
    service: CollaborationApplicationService,
    ids: FixtureIds,
    endpoint: CollaborationEndpoint,
    *,
    actor_id: str | None = None,
) -> ExternalActorMapping:
    identity = _ref(
        ids,
        object_type="actor_identity",
        external_object_id=f"ext-{actor_id or ids.human_owner}",
        locator="memory://actors/owner",
    )
    service.save_external_reference(identity)
    mapping = ExternalActorMapping(
        mapping_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        endpoint_id=endpoint.endpoint_id,
        actor_id=actor_id or ids.human_owner,
        provider="memory",
        external_actor_id=identity.external_object_id,
        external_identity_reference_id=identity.reference_id,
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_actor_mapping(mapping)
    return mapping


def _ref(
    ids: FixtureIds,
    *,
    object_type: str,
    external_object_id: str,
    locator: str,
    tenant_id: str | None = None,
) -> ExternalReference:
    return ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=tenant_id or ids.tenant_alpha,
        provider="memory",
        object_type=object_type,
        external_object_id=external_object_id,
        locator=locator,
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )


def _origin_bundle(
    ids: FixtureIds,
    *,
    endpoint_id: str,
    mapping: ExternalActorMapping,
    external_event_id: str = "evt-origin-1",
    subject: str = "fix flaky claim race",
    actor_id: str | None = None,
    tenant_id: str | None = None,
    verification_result: VerificationResult = VerificationResult.VERIFIED,
    mapping_id: str | None = None,
    external_actor_id: str | None = None,
):
    tenant = tenant_id or ids.tenant_alpha
    source = _ref(
        ids,
        object_type="collaboration_event",
        external_object_id=external_event_id,
        locator=f"memory://events/{external_event_id}",
        tenant_id=tenant,
    )
    location = _ref(
        ids,
        object_type="conversation_thread",
        external_object_id="thread-1",
        locator="memory://channels/main/threads/1",
        tenant_id=tenant,
    )
    parent = _ref(
        ids,
        object_type="conversation_channel",
        external_object_id="channel-main",
        locator="memory://channels/main",
        tenant_id=tenant,
    )
    origin_id = generate_uuidv7()
    receipt_id = generate_uuidv7()
    body = f"@holodeck work: {subject}"
    resolved_mapping_id = mapping_id or mapping.mapping_id
    resolved_external_actor_id = external_actor_id or mapping.external_actor_id
    receipt = InboundEventReceipt(
        receipt_id=receipt_id,
        tenant_id=tenant,
        provider="memory",
        external_event_id=external_event_id,
        inbound_event_id=generate_uuidv7(),
        signed_source_reference_id=source.reference_id,
        verification_result=verification_result,
        processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
        reason_codes=("reason.allowed",),
        checkpoint_token=generate_uuidv7(),
        created_at=NOW,
        task_origin_object_id=origin_id,
        mapping_id=resolved_mapping_id,
        external_actor_id=resolved_external_actor_id,
    )
    origin = TaskOrigin(
        object_id=origin_id,
        tenant_id=tenant,
        actor_id=actor_id or ids.human_owner,
        inbound_receipt_id=receipt_id,
        source_reference_id=source.reference_id,
        provider="memory",
        external_event_id=external_event_id,
        subject_text=subject,
        body_text=body,
        location_kind=LocationKind.THREAD,
        location_reference_id=location.reference_id,
        parent_location_reference_id=parent.reference_id,
        endpoint_id=endpoint_id,
        mapping_id=resolved_mapping_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
        adapter_metadata={"thread_title": "claims"},
    )
    return origin, receipt, source, location, parent


def test_migrate_v12_creates_task_origins_table() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    assert governance_schema_version(conn) == 17
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "gov_task_origins" in tables
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(gov_task_origins)").fetchall()
    }
    assert "mapping_id" in columns


def test_accept_task_origin_persists_source_thread_context_cis008() -> None:
    conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    mapping = _bind_actor(service, ids, endpoint)
    origin, receipt, source, location, parent = _origin_bundle(
        ids, endpoint_id=endpoint.endpoint_id, mapping=mapping
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
    assert result.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
    assert result.origin.subject_text == "fix flaky claim race"
    assert result.origin.location_kind is LocationKind.THREAD
    assert result.origin.parent_location_reference_id == parent.reference_id
    assert result.origin.mapping_id == mapping.mapping_id
    assert result.receipt.task_origin_object_id == origin.object_id
    assert result.receipt.mapping_id == mapping.mapping_id
    assert result.receipt.external_actor_id == mapping.external_actor_id
    loaded = service.get_task_origin(origin.object_id)
    assert loaded == result.origin
    assert conn.execute("SELECT COUNT(*) FROM gov_task_origins").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_missions").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_runs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_approvals").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 0


def test_duplicate_accept_replays_same_origin_cis003_origin_slice() -> None:
    conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    mapping = _bind_actor(service, ids, endpoint)
    origin, receipt, source, location, parent = _origin_bundle(
        ids, endpoint_id=endpoint.endpoint_id, mapping=mapping
    )
    first = service.accept_task_origin(
        origin=origin,
        receipt=receipt,
        source_reference=source,
        location_reference=location,
        parent_location_reference=parent,
        endpoint_id=endpoint.endpoint_id,
    )
    retry_origin, retry_receipt, _s, _l, _p = _origin_bundle(
        ids,
        endpoint_id=endpoint.endpoint_id,
        mapping=mapping,
        external_event_id=origin.external_event_id,
    )
    retry_receipt = InboundEventReceipt(
        receipt_id=retry_receipt.receipt_id,
        tenant_id=retry_receipt.tenant_id,
        provider=retry_receipt.provider,
        external_event_id=origin.external_event_id,
        inbound_event_id=retry_receipt.inbound_event_id,
        signed_source_reference_id=source.reference_id,
        verification_result=VerificationResult.VERIFIED,
        processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
        reason_codes=("reason.allowed",),
        checkpoint_token=retry_receipt.checkpoint_token,
        created_at=NOW,
        task_origin_object_id=retry_origin.object_id,
        mapping_id=mapping.mapping_id,
        external_actor_id=mapping.external_actor_id,
    )
    retry_origin = TaskOrigin(
        object_id=retry_origin.object_id,
        tenant_id=origin.tenant_id,
        actor_id=origin.actor_id,
        inbound_receipt_id=retry_receipt.receipt_id,
        source_reference_id=source.reference_id,
        provider="memory",
        external_event_id=origin.external_event_id,
        subject_text="different subject ignored on replay",
        body_text="@holodeck work: different subject ignored on replay",
        location_kind=LocationKind.THREAD,
        location_reference_id=location.reference_id,
        parent_location_reference_id=parent.reference_id,
        endpoint_id=endpoint.endpoint_id,
        mapping_id=mapping.mapping_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    second = service.accept_task_origin(
        origin=retry_origin,
        receipt=retry_receipt,
        source_reference=source,
        location_reference=location,
        parent_location_reference=parent,
        endpoint_id=endpoint.endpoint_id,
    )
    assert first.created is True
    assert second.created is False
    assert second.processing_outcome is ProcessingOutcome.DUPLICATE_REPLAY
    assert second.origin.object_id == first.origin.object_id
    assert second.receipt.receipt_id == first.receipt.receipt_id
    assert conn.execute("SELECT COUNT(*) FROM gov_task_origins").fetchone()[0] == 1
    assert (
        conn.execute("SELECT COUNT(*) FROM gov_inbound_event_receipts").fetchone()[0] == 1
    )


def test_cross_tenant_origin_actor_rejected() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    mapping = _bind_actor(service, ids, endpoint)
    origin, receipt, source, location, parent = _origin_bundle(
        ids,
        endpoint_id=endpoint.endpoint_id,
        mapping=mapping,
        actor_id=ids.human_reviewer,
    )
    with pytest.raises((CrossTenantAccessError, MissingAuthorityError)):
        service.accept_task_origin(
            origin=origin,
            receipt=receipt,
            source_reference=source,
            location_reference=location,
            parent_location_reference=parent,
            endpoint_id=endpoint.endpoint_id,
        )


def test_unverified_actor_cannot_create_origin() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    mapping = _bind_actor(service, ids, endpoint)
    origin, receipt, source, location, parent = _origin_bundle(
        ids,
        endpoint_id=endpoint.endpoint_id,
        mapping=mapping,
        verification_result=VerificationResult.FAILED,
    )
    with pytest.raises(MissingAuthorityError):
        service.accept_task_origin(
            origin=origin,
            receipt=receipt,
            source_reference=source,
            location_reference=location,
            parent_location_reference=parent,
            endpoint_id=endpoint.endpoint_id,
        )


def test_record_inbound_receipt_rejects_accepted_origin_shortcut() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    mapping = _bind_actor(service, ids, endpoint)
    origin, receipt, source, _location, _parent = _origin_bundle(
        ids, endpoint_id=endpoint.endpoint_id, mapping=mapping
    )
    with pytest.raises(MalformedCommandError):
        service.record_inbound_receipt(receipt, source_reference=source)


def test_accept_rejects_mismatched_sender_mapping_attribution() -> None:
    conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    owner_mapping = _bind_actor(service, ids, endpoint)
    other_actor_id = generate_uuidv7()
    auth = SqliteAuthorityRepository(conn)
    auth.save_actor(
        Actor(
            actor_id=other_actor_id,
            tenant_id=ids.tenant_alpha,
            kind=ActorKind.HUMAN,
            display_name="Other",
            created_at=FIXED_CLOCK,
            created_by_actor_id=ids.system_service,
        )
    )
    _grant_intake_authority(conn, ids, actor_id=other_actor_id)
    other_mapping = _bind_actor(service, ids, endpoint, actor_id=other_actor_id)

    # Verified sender is "other", but origin attributes via owner's mapping/actor.
    origin, receipt, source, location, parent = _origin_bundle(
        ids,
        endpoint_id=endpoint.endpoint_id,
        mapping=owner_mapping,
        actor_id=ids.human_owner,
        external_actor_id=other_mapping.external_actor_id,
    )
    with pytest.raises(MissingAuthorityError):
        service.accept_task_origin(
            origin=origin,
            receipt=receipt,
            source_reference=source,
            location_reference=location,
            parent_location_reference=parent,
            endpoint_id=endpoint.endpoint_id,
        )

    # Sender external id matches other mapping, but claimed Holodeck actor is owner.
    origin, receipt, source, location, parent = _origin_bundle(
        ids,
        endpoint_id=endpoint.endpoint_id,
        mapping=other_mapping,
        actor_id=ids.human_owner,
        external_event_id="evt-misattrib-2",
    )
    with pytest.raises(MissingAuthorityError):
        service.accept_task_origin(
            origin=origin,
            receipt=receipt,
            source_reference=source,
            location_reference=location,
            parent_location_reference=parent,
            endpoint_id=endpoint.endpoint_id,
        )
    assert conn.execute("SELECT COUNT(*) FROM gov_task_origins").fetchone()[0] == 0
