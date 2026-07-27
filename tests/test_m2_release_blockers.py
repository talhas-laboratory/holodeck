"""Adversarial coverage for M2 collaboration release blockers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.composition import open_collaboration_app
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
from holodeck_governance.domain.errors import MissingAuthorityError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.collaboration import SqliteCollaborationRepository
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)


def _seed_tenants_and_actors(conn: sqlite3.Connection, ids: FixtureIds) -> None:
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
    for actor_id, tenant_id, name in (
        (ids.human_owner, ids.tenant_alpha, "Owner"),
        (ids.system_service, ids.tenant_alpha, "System"),
        (ids.human_reviewer, ids.tenant_beta, "Beta"),
    ):
        auth.save_actor(
            Actor(
                actor_id=actor_id,
                tenant_id=tenant_id,
                kind=ActorKind.HUMAN if actor_id != ids.system_service else ActorKind.SERVICE,
                display_name=name,
                created_at=FIXED_CLOCK,
                created_by_actor_id=ids.system_service,
            )
        )
    conn.commit()


def test_open_collaboration_app_commits_are_visible_to_second_connection(
    tmp_path: Path,
) -> None:
    db = tmp_path / "collab.db"
    ids = FixtureIds()
    bootstrap = sqlite3.connect(db)
    bootstrap.row_factory = sqlite3.Row
    _seed_tenants_and_actors(bootstrap, ids)
    bootstrap.close()

    app = open_collaboration_app(str(db))
    endpoint = CollaborationEndpoint(
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
    app.save_endpoint(endpoint)

    other = sqlite3.connect(db)
    other.row_factory = sqlite3.Row
    count = other.execute(
        "SELECT COUNT(*) AS n FROM gov_collaboration_endpoints WHERE endpoint_id = ?",
        (endpoint.endpoint_id,),
    ).fetchone()["n"]
    assert int(count) == 1


def test_accept_task_origin_rejects_failed_verification_without_mapping() -> None:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_tenants_and_actors(conn, ids)
    service = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )
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
    source = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        object_type="collaboration_event",
        external_object_id="evt-bad",
        locator="memory://events/evt-bad",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    location = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        object_type="conversation_thread",
        external_object_id="thread-bad",
        locator="memory://threads/bad",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    origin_id = generate_uuidv7()
    receipt_id = generate_uuidv7()
    receipt = InboundEventReceipt(
        receipt_id=receipt_id,
        tenant_id=ids.tenant_alpha,
        provider="memory",
        external_event_id="evt-bad",
        inbound_event_id=generate_uuidv7(),
        signed_source_reference_id=source.reference_id,
        verification_result=VerificationResult.FAILED,
        processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
        reason_codes=("reason.allowed",),
        checkpoint_token=generate_uuidv7(),
        created_at=NOW,
        task_origin_object_id=origin_id,
    )
    origin = TaskOrigin(
        object_id=origin_id,
        tenant_id=ids.tenant_alpha,
        actor_id=ids.human_owner,
        inbound_receipt_id=receipt_id,
        source_reference_id=source.reference_id,
        provider="memory",
        external_event_id="evt-bad",
        subject_text="should fail",
        body_text="@holodeck work: should fail",
        location_kind=LocationKind.THREAD,
        location_reference_id=location.reference_id,
        endpoint_id=endpoint.endpoint_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    with pytest.raises(MissingAuthorityError):
        service.accept_task_origin(
            origin=origin,
            receipt=receipt,
            source_reference=source,
            location_reference=location,
            endpoint_id=endpoint.endpoint_id,
        )
    assert conn.execute("SELECT COUNT(*) FROM gov_task_origins").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM gov_external_actor_mappings"
    ).fetchone()[0] == 0


def test_raw_sql_cross_tenant_actor_mapping_is_aborted() -> None:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_tenants_and_actors(conn, ids)
    conn.execute("PRAGMA foreign_keys = ON")
    service = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )
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
    identity = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        object_type="actor_identity",
        external_object_id="ext-cross",
        locator="memory://actors/cross",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_external_reference(identity)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO gov_external_actor_mappings(
                mapping_id, tenant_id, endpoint_id, actor_id, provider, external_actor_id,
                external_identity_reference_id, status, created_at, created_by_actor_id,
                adapter_metadata_json, schema_version
            ) VALUES (?, ?, ?, ?, 'memory', 'ext-cross', ?, 'active', ?, ?, '{}', 'm2.external_actor_mapping.v1')
            """,
            (
                generate_uuidv7(),
                ids.tenant_alpha,
                endpoint.endpoint_id,
                ids.human_reviewer,  # beta actor
                identity.reference_id,
                NOW.isoformat(),
                ids.system_service,
            ),
        )
    assert (
        conn.execute("SELECT COUNT(*) FROM gov_external_actor_mappings").fetchone()[0]
        == 0
    )
