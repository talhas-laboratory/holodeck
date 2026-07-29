"""M2-010 end-to-end intake via memory adapter + Holodeck collaboration seam."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from holodeck_governance.adapters.collaboration import (
    MEMORY_PROVIDER,
    InMemoryCollaborationAdapter,
    MemoryExternalActor,
)
from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.application.collaboration_intake import (
    CollaborationIntakeOrchestrator,
)
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
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.collaboration import SqliteCollaborationRepository
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
EXT_OWNER = "ext-owner"
EXT_UNAUTHORIZED = "ext-noauth"


@dataclass(slots=True)
class E2EWorld:
    conn: sqlite3.Connection
    ids: FixtureIds
    service: CollaborationApplicationService
    adapter: InMemoryCollaborationAdapter
    orchestrator: CollaborationIntakeOrchestrator
    endpoint: CollaborationEndpoint
    beta_endpoint: CollaborationEndpoint
    unauthorized_actor_id: str


def _grant_intake(conn: sqlite3.Connection, ids: FixtureIds, *, actor_id: str) -> None:
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


def _world(*, grant_owner_intake: bool = True) -> E2EWorld:
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
    unauthorized_actor_id = generate_uuidv7()
    beta_service_id = generate_uuidv7()
    for actor_id, tenant_id, name, kind in (
        (ids.human_owner, ids.tenant_alpha, "Owner", ActorKind.HUMAN),
        (ids.system_service, ids.tenant_alpha, "System", ActorKind.SERVICE),
        (unauthorized_actor_id, ids.tenant_alpha, "NoAuth", ActorKind.HUMAN),
        (ids.human_reviewer, ids.tenant_beta, "Beta", ActorKind.HUMAN),
        (beta_service_id, ids.tenant_beta, "BetaSystem", ActorKind.SERVICE),
    ):
        auth.save_actor(
            Actor(
                actor_id=actor_id,
                tenant_id=tenant_id,
                kind=kind,
                display_name=name,
                created_at=FIXED_CLOCK,
                created_by_actor_id=ids.system_service,
            )
        )
    if grant_owner_intake:
        _grant_intake(conn, ids, actor_id=ids.human_owner)

    service = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )
    endpoint = CollaborationEndpoint(
        endpoint_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider=MEMORY_PROVIDER,
        external_endpoint_id="community-alpha",
        locator="memory://community-alpha",
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_endpoint(endpoint)
    beta_endpoint = CollaborationEndpoint(
        endpoint_id=generate_uuidv7(),
        tenant_id=ids.tenant_beta,
        provider=MEMORY_PROVIDER,
        external_endpoint_id="community-beta",
        locator="memory://community-beta",
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=beta_service_id,
    )
    service.save_endpoint(beta_endpoint)

    for external_actor_id, actor_id, locator in (
        (EXT_OWNER, ids.human_owner, "memory://actors/ext-owner"),
        (EXT_UNAUTHORIZED, unauthorized_actor_id, "memory://actors/ext-noauth"),
    ):
        identity = ExternalReference(
            reference_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            provider=MEMORY_PROVIDER,
            object_type="external_actor",
            external_object_id=external_actor_id,
            locator=locator,
            observed_at=NOW,
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
        service.save_external_reference(identity)
        service.save_actor_mapping(
            ExternalActorMapping(
                mapping_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                endpoint_id=endpoint.endpoint_id,
                actor_id=actor_id,
                provider=MEMORY_PROVIDER,
                external_actor_id=external_actor_id,
                external_identity_reference_id=identity.reference_id,
                status=BindingStatus.ACTIVE,
                created_at=NOW,
                created_by_actor_id=ids.system_service,
            )
        )

    adapter = InMemoryCollaborationAdapter(
        created_by_actor_id=ids.system_service,
        clock=lambda: NOW,
        id_factory=generate_uuidv7,
    )
    adapter.register_actor(
        MemoryExternalActor(
            external_actor_id=EXT_OWNER,
            tenant_id=ids.tenant_alpha,
            actor_id=ids.human_owner,
            identity_locator="memory://actors/ext-owner",
        )
    )
    adapter.register_actor(
        MemoryExternalActor(
            external_actor_id=EXT_UNAUTHORIZED,
            tenant_id=ids.tenant_alpha,
            actor_id=unauthorized_actor_id,
            identity_locator="memory://actors/ext-noauth",
        )
    )
    orchestrator = CollaborationIntakeOrchestrator(
        adapter=adapter,
        collaboration=service,
        created_by_actor_id=ids.system_service,
        clock=lambda: NOW,
        id_factory=generate_uuidv7,
    )
    return E2EWorld(
        conn=conn,
        ids=ids,
        service=service,
        adapter=adapter,
        orchestrator=orchestrator,
        endpoint=endpoint,
        beta_endpoint=beta_endpoint,
        unauthorized_actor_id=unauthorized_actor_id,
    )


def _payload(world: E2EWorld, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "tenant_id": world.ids.tenant_alpha,
        "external_event_id": "evt-e2e-1",
        "external_actor_id": EXT_OWNER,
        "body_text": "@holodeck work: prove e2e intake",
        "location_kind": "channel",
        "external_location_id": "channel-main",
        "location_locator": "memory://channels/main",
        "parent_location_kind": "community",
        "parent_external_location_id": "community-alpha",
        "signature": "ok",
        "occurred_at": NOW.isoformat(),
        "endpoint_id": world.endpoint.endpoint_id,
    }
    base.update(overrides)
    return base


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "receipts": int(
            conn.execute("SELECT COUNT(*) FROM gov_inbound_event_receipts").fetchone()[0]
        ),
        "origins": int(conn.execute("SELECT COUNT(*) FROM gov_task_origins").fetchone()[0]),
        "outbound": int(
            conn.execute(
                "SELECT COUNT(*) FROM gov_outbound_collaboration_messages"
            ).fetchone()[0]
        ),
        "outbox": int(
            conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0]
        ),
        "missions": int(
            conn.execute(
                "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Mission'"
            ).fetchone()[0]
        ),
        "runs": int(
            conn.execute(
                "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Run'"
            ).fetchone()[0]
        ),
    }


def test_cis001_auth_failure_creates_no_governed_state() -> None:
    world = _world()
    result = world.orchestrator.handle_inbound(_payload(world, signature="bad"))
    assert result.processing_outcome is ProcessingOutcome.AUTH_FAILED
    assert result.verification_result is VerificationResult.FAILED
    assert result.receipt is None
    assert _counts(world.conn) == {
        "receipts": 0,
        "origins": 0,
        "outbound": 0,
        "outbox": 0,
        "missions": 0,
        "runs": 0,
    }


def test_cis002_unauthorized_records_rejected_receipt_only() -> None:
    world = _world()
    result = world.orchestrator.handle_inbound(
        _payload(
            world,
            external_event_id="evt-unauth",
            external_actor_id=EXT_UNAUTHORIZED,
            body_text="@holodeck work: denied",
        )
    )
    assert result.processing_outcome is ProcessingOutcome.REJECTED
    assert result.receipt is not None
    assert "reason.missing_authority" in result.receipt.reason_codes
    counts = _counts(world.conn)
    assert counts["receipts"] == 1
    assert counts["origins"] == 0
    assert counts["outbound"] == 0


def test_cis003_and_cis004_duplicate_replay_preserves_single_origin() -> None:
    world = _world()
    first = world.orchestrator.handle_inbound(_payload(world))
    assert first.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
    assert first.created is True
    assert first.origin is not None
    assert first.outbound_message is not None
    assert first.outbound_ack is not None

    replay = world.orchestrator.handle_inbound(_payload(world))
    assert replay.processing_outcome is ProcessingOutcome.DUPLICATE_REPLAY
    assert replay.created is False
    assert replay.receipt is not None
    assert replay.receipt.receipt_id == first.receipt.receipt_id
    assert replay.origin is not None
    assert replay.origin.object_id == first.origin.object_id

    counts = _counts(world.conn)
    assert counts["receipts"] == 1
    assert counts["origins"] == 1
    assert counts["outbound"] == 1
    assert len(world.adapter.published_messages) == 1


def test_cis005_cross_tenant_endpoint_is_rejected() -> None:
    world = _world()
    result = world.orchestrator.handle_inbound(
        _payload(
            world,
            external_event_id="evt-xtenant",
            endpoint_id=world.beta_endpoint.endpoint_id,
        )
    )
    assert result.processing_outcome is ProcessingOutcome.REJECTED
    assert result.receipt is not None
    assert "reason.cross_tenant_denied" in result.receipt.reason_codes
    assert _counts(world.conn)["origins"] == 0
    assert _counts(world.conn)["outbound"] == 0


def test_cis006_ordinary_chat_is_ignored_non_intake() -> None:
    world = _world()
    result = world.orchestrator.handle_inbound(
        _payload(
            world,
            external_event_id="evt-chat",
            body_text="hello team, ignoring this",
        )
    )
    assert result.processing_outcome is ProcessingOutcome.IGNORED_NON_INTAKE
    assert result.receipt is not None
    counts = _counts(world.conn)
    assert counts["receipts"] == 1
    assert counts["origins"] == 0
    assert counts["outbound"] == 0


def test_cis007_and_cis008_happy_path_correlates_status_without_mission() -> None:
    world = _world()
    result = world.orchestrator.handle_inbound(_payload(world, external_event_id="evt-ok"))
    assert result.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
    assert result.origin is not None
    assert result.receipt is not None
    assert result.outbound_message is not None
    assert result.outbound_message.task_origin_object_id == result.origin.object_id
    assert result.outbound_message.inbound_receipt_id == result.receipt.receipt_id
    assert result.outbox_item_id is not None
    assert result.outbound_ack is not None
    assert result.outbound_ack["status"] == "delivered"

    counts = _counts(world.conn)
    assert counts == {
        "receipts": 1,
        "origins": 1,
        "outbound": 1,
        "outbox": 1,
        "missions": 0,
        "runs": 0,
    }
    # Re-publish same semantic status through adapter remains idempotent.
    again = world.adapter.publish_outbound(result.outbound_message)
    assert again == result.outbound_ack
    assert len(world.adapter.published_messages) == 1


def test_crash_between_origin_and_outbox_is_repaired_on_retry() -> None:
    """Origin commit without outbound; retry completes exactly-once outbox work."""

    world = _world()
    payload = _payload(world, external_event_id="evt-crash-gap")
    mapping = world.service.resolve_actor_mapping(
        tenant_id=world.ids.tenant_alpha,
        provider=MEMORY_PROVIDER,
        external_actor_id=EXT_OWNER,
    )
    assert mapping is not None

    source = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=world.ids.tenant_alpha,
        provider=MEMORY_PROVIDER,
        object_type="collaboration_event",
        external_object_id="evt-crash-gap",
        locator="memory://events/evt-crash-gap",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=world.ids.system_service,
    )
    location = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=world.ids.tenant_alpha,
        provider=MEMORY_PROVIDER,
        object_type="conversation_channel",
        external_object_id="channel-main",
        locator="memory://channels/main",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=world.ids.system_service,
    )
    origin_id = generate_uuidv7()
    receipt_id = generate_uuidv7()
    # Simulate crash after origin+receipt commit, before outbound/outbox.
    crashed = world.service.accept_task_origin(
        origin=TaskOrigin(
            object_id=origin_id,
            tenant_id=world.ids.tenant_alpha,
            actor_id=world.ids.human_owner,
            inbound_receipt_id=receipt_id,
            source_reference_id=source.reference_id,
            provider=MEMORY_PROVIDER,
            external_event_id="evt-crash-gap",
            subject_text="prove e2e intake",
            body_text=str(payload["body_text"]),
            location_kind=LocationKind.CHANNEL,
            location_reference_id=location.reference_id,
            created_at=NOW,
            created_by_actor_id=world.ids.system_service,
            mapping_id=mapping.mapping_id,
            endpoint_id=world.endpoint.endpoint_id,
        ),
        receipt=InboundEventReceipt(
            receipt_id=receipt_id,
            tenant_id=world.ids.tenant_alpha,
            provider=MEMORY_PROVIDER,
            external_event_id="evt-crash-gap",
            inbound_event_id=generate_uuidv7(),
            signed_source_reference_id=source.reference_id,
            verification_result=VerificationResult.VERIFIED,
            processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
            reason_codes=("reason.accepted_origin",),
            checkpoint_token=generate_uuidv7(),
            created_at=NOW,
            command_id=generate_uuidv7(),
            task_origin_object_id=origin_id,
            mapping_id=mapping.mapping_id,
            external_actor_id=mapping.external_actor_id,
        ),
        source_reference=source,
        location_reference=location,
        endpoint_id=world.endpoint.endpoint_id,
    )
    assert crashed.created is True
    assert _counts(world.conn)["origins"] == 1
    assert _counts(world.conn)["outbound"] == 0
    assert _counts(world.conn)["outbox"] == 0

    repaired = world.orchestrator.handle_inbound(payload)
    assert repaired.processing_outcome is ProcessingOutcome.DUPLICATE_REPLAY
    assert repaired.created is False
    assert repaired.origin is not None
    assert repaired.origin.object_id == origin_id
    assert repaired.outbound_message is not None
    assert repaired.outbox_item_id is not None
    assert repaired.outbound_ack is not None

    counts = _counts(world.conn)
    assert counts["receipts"] == 1
    assert counts["origins"] == 1
    assert counts["outbound"] == 1
    assert counts["outbox"] == 1
    assert len(world.adapter.published_messages) == 1

    again = world.orchestrator.handle_inbound(payload)
    assert again.processing_outcome is ProcessingOutcome.DUPLICATE_REPLAY
    assert _counts(world.conn)["receipts"] == 1
    assert _counts(world.conn)["origins"] == 1
    assert _counts(world.conn)["outbound"] == 1
    assert _counts(world.conn)["outbox"] == 1
    assert len(world.adapter.published_messages) == 1


def test_unsigned_payload_is_auth_failed() -> None:
    world = _world()
    result = world.orchestrator.handle_inbound(_payload(world, signature=""))
    assert result.processing_outcome is ProcessingOutcome.AUTH_FAILED
    assert result.verification_result is VerificationResult.UNSIGNED
