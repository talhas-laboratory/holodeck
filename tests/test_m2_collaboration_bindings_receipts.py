"""M2-002 collaboration bindings, actor mappings, and durable receipts."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.composition import open_collaboration_app
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.collaboration import (
    BindingStatus,
    CollaborationEndpoint,
    ExternalActorMapping,
    InboundEventReceipt,
    ProcessingOutcome,
    VerificationResult,
)
from holodeck_governance.domain.errors import CrossTenantAccessError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.collaboration import SqliteCollaborationRepository
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
)
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FixtureIds, FIXED_CLOCK

NOW = datetime(2026, 7, 27, 13, 0, tzinfo=UTC)


def _service() -> tuple[sqlite3.Connection, CollaborationApplicationService, FixtureIds]:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_governance(conn)
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    # Beta tenant for isolation tests
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
    service = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )
    return conn, service, ids


def _endpoint(ids: FixtureIds, *, endpoint_id: str | None = None) -> CollaborationEndpoint:
    return CollaborationEndpoint(
        endpoint_id=endpoint_id or generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        external_endpoint_id="community-alpha",
        locator="memory://community-alpha",
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
        display_name="Alpha community",
        adapter_metadata={"relay": "local"},
    )


def _identity_ref(ids: FixtureIds, *, reference_id: str | None = None) -> ExternalReference:
    return ExternalReference(
        reference_id=reference_id or generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        object_type="actor_identity",
        external_object_id="ext-actor-1",
        locator="memory://actors/ext-actor-1",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )


def _source_ref(
    ids: FixtureIds, *, reference_id: str | None = None, external_event_id: str = "evt-1"
) -> ExternalReference:
    return ExternalReference(
        reference_id=reference_id or generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        object_type="collaboration_event",
        external_object_id=external_event_id,
        locator=f"memory://events/{external_event_id}",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )


def _receipt(
    ids: FixtureIds,
    *,
    source_reference_id: str,
    outcome: ProcessingOutcome,
    external_event_id: str = "evt-1",
    receipt_id: str | None = None,
) -> InboundEventReceipt:
    return InboundEventReceipt(
        receipt_id=receipt_id or generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        external_event_id=external_event_id,
        inbound_event_id=generate_uuidv7(),
        signed_source_reference_id=source_reference_id,
        verification_result=VerificationResult.VERIFIED,
        processing_outcome=outcome,
        reason_codes=(
            ("reason.allowed",)
            if outcome is not ProcessingOutcome.REJECTED
            else ("reason.deny.missing_authority",)
        ),
        checkpoint_token=generate_uuidv7(),
        created_at=NOW,
    )


def test_migrate_v11_creates_collaboration_tables() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    assert governance_schema_version(conn) == 24
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "gov_collaboration_endpoints" in tables
    assert "gov_external_actor_mappings" in tables
    assert "gov_inbound_event_receipts" in tables


def test_open_collaboration_app_composition(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = tmp_path / "gov.db"
    service = open_collaboration_app(str(db))
    assert isinstance(service, CollaborationApplicationService)


def test_save_endpoint_and_actor_mapping() -> None:
    conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    identity = _identity_ref(ids)
    service.save_external_reference(identity)
    mapping = ExternalActorMapping(
        mapping_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        endpoint_id=endpoint.endpoint_id,
        actor_id=ids.human_owner,
        provider="memory",
        external_actor_id="ext-actor-1",
        external_identity_reference_id=identity.reference_id,
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_actor_mapping(mapping)
    resolved = service.resolve_actor_mapping(
        tenant_id=ids.tenant_alpha,
        provider="memory",
        external_actor_id="ext-actor-1",
    )
    assert resolved is not None
    assert resolved.actor_id == ids.human_owner
    assert service.get_endpoint(endpoint.endpoint_id) == endpoint


def test_cross_tenant_actor_mapping_rejected() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    identity = _identity_ref(ids)
    service.save_external_reference(identity)
    with pytest.raises(CrossTenantAccessError):
        service.save_actor_mapping(
            ExternalActorMapping(
                mapping_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                endpoint_id=endpoint.endpoint_id,
                actor_id=ids.human_reviewer,  # beta actor
                provider="memory",
                external_actor_id="ext-actor-x",
                external_identity_reference_id=identity.reference_id,
                status=BindingStatus.ACTIVE,
                created_at=NOW,
                created_by_actor_id=ids.system_service,
            )
        )


def test_record_rejected_receipt_without_origin_cis002() -> None:
    conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    source = _source_ref(ids)
    result = service.record_inbound_receipt(
        _receipt(ids, source_reference_id=source.reference_id, outcome=ProcessingOutcome.REJECTED),
        source_reference=source,
        endpoint_id=endpoint.endpoint_id,
    )
    assert result.created is True
    assert result.processing_outcome is ProcessingOutcome.REJECTED
    assert result.receipt.task_origin_object_id is None
    assert conn.execute("SELECT COUNT(*) FROM gov_task_origins").fetchone()[0] == 0
    assert (
        conn.execute("SELECT COUNT(*) FROM gov_inbound_event_receipts").fetchone()[0] == 1
    )
    assert conn.execute("SELECT COUNT(*) FROM gov_missions").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_runs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_approvals").fetchone()[0] == 0


def test_ignored_non_intake_receipt_cis006() -> None:
    _conn, service, ids = _service()
    source = _source_ref(ids, external_event_id="chat-9")
    result = service.record_inbound_receipt(
        _receipt(
            ids,
            source_reference_id=source.reference_id,
            outcome=ProcessingOutcome.IGNORED_NON_INTAKE,
            external_event_id="chat-9",
        ),
        source_reference=source,
    )
    assert result.created is True
    assert result.processing_outcome is ProcessingOutcome.IGNORED_NON_INTAKE
    assert result.receipt.task_origin_object_id is None


def test_duplicate_delivery_returns_prior_receipt_cis003() -> None:
    conn, service, ids = _service()
    source = _source_ref(ids)
    first = service.record_inbound_receipt(
        _receipt(
            ids,
            source_reference_id=source.reference_id,
            outcome=ProcessingOutcome.IGNORED_NON_INTAKE,
        ),
        source_reference=source,
    )
    second = service.record_inbound_receipt(
        _receipt(
            ids,
            source_reference_id=source.reference_id,
            outcome=ProcessingOutcome.REJECTED,
            receipt_id=generate_uuidv7(),
        ),
        source_reference=source,
    )
    assert first.created is True
    assert second.created is False
    assert second.processing_outcome is ProcessingOutcome.DUPLICATE_REPLAY
    assert second.receipt.receipt_id == first.receipt.receipt_id
    assert second.receipt.processing_outcome is ProcessingOutcome.IGNORED_NON_INTAKE
    assert (
        conn.execute("SELECT COUNT(*) FROM gov_inbound_event_receipts").fetchone()[0] == 1
    )


def test_crash_retry_converges_on_single_receipt_cis004_receipt_slice() -> None:
    conn, service, ids = _service()
    source = _source_ref(ids, external_event_id="evt-retry")
    receipt = _receipt(
        ids,
        source_reference_id=source.reference_id,
        outcome=ProcessingOutcome.IGNORED_NON_INTAKE,
        external_event_id="evt-retry",
    )
    first = service.record_inbound_receipt(receipt, source_reference=source)
    # Simulate retry with identical external id after checkpoint.
    retry = service.record_inbound_receipt(receipt, source_reference=source)
    assert first.created is True
    assert retry.created is False
    assert retry.receipt.checkpoint_token == first.receipt.checkpoint_token
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_inbound_event_receipts WHERE external_event_id = ?",
            ("evt-retry",),
        ).fetchone()[0]
        == 1
    )
