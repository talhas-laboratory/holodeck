"""Tests for grants, edges, and remaining typed records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from holodeck_governance.domain.authority.grants import (
    DelegatedGrant,
    GrantExpiredError,
    GrantRevokedError,
    GrantWrongRevisionError,
    RevocationDecision,
    assert_grant_authorizes,
)
from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.edges import TraceabilityEdge, validate_edge_endpoints
from holodeck_governance.domain.errors import CrossTenantAccessError, EdgeValidationError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records.approval import ApprovalRecord
from holodeck_governance.domain.records.evidence import EvidenceRecord
from holodeck_governance.domain.records.requirement import RequirementRecord
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.testing import FixtureIds


def test_delegated_grant_active_expired_revoked_wrong_revision_gs004() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    grant = DelegatedGrant(
        grant_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        delegator_actor_id=ids.human_owner,
        recipient_actor_id=ids.worker_agent,
        permission="transition_task",
        subject_object_id=ids.mission_object,
        subject_revision=3,
        effective_from=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    assert_grant_authorizes(
        grant,
        at=now,
        recipient_actor_id=ids.worker_agent,
        subject_object_id=ids.mission_object,
        subject_revision=3,
        permission="transition_task",
    )
    with pytest.raises(GrantExpiredError):
        assert_grant_authorizes(
            grant,
            at=now + timedelta(hours=2),
            recipient_actor_id=ids.worker_agent,
            subject_object_id=ids.mission_object,
            subject_revision=3,
            permission="transition_task",
        )
    with pytest.raises(GrantWrongRevisionError):
        assert_grant_authorizes(
            grant,
            at=now,
            recipient_actor_id=ids.worker_agent,
            subject_object_id=ids.mission_object,
            subject_revision=4,
            permission="transition_task",
        )
    revocation = RevocationDecision(
        revocation_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        grant_id=grant.grant_id,
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    with pytest.raises(GrantRevokedError):
        assert_grant_authorizes(
            grant,
            at=now,
            recipient_actor_id=ids.worker_agent,
            subject_object_id=ids.mission_object,
            subject_revision=3,
            permission="transition_task",
            revocation=revocation,
        )


def test_edge_matrix_rejects_missing_incompatible_cross_tenant_gs005() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    edge = TraceabilityEdge(
        edge_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        edge_type="evidence_supports_requirement",
        from_object_id=generate_uuidv7(),
        from_revision=1,
        to_object_id=ids.requirement_object,
        to_revision=1,
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    with pytest.raises(EdgeValidationError) as missing:
        validate_edge_endpoints(edge, from_object=None, to_object=None)
    assert missing.value.code == DomainErrorCode.EDGE_ENDPOINT_MISSING

    evidence = GovernanceObject(
        object_id=edge.from_object_id,
        tenant_id=ids.tenant_alpha,
        object_type="Evidence",
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    requirement = GovernanceObject(
        object_id=ids.requirement_object,
        tenant_id=ids.tenant_alpha,
        object_type="Requirement",
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    validate_edge_endpoints(edge, from_object=evidence, to_object=requirement)

    bad_from = GovernanceObject(
        object_id=edge.from_object_id,
        tenant_id=ids.tenant_alpha,
        object_type="Mission",
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    with pytest.raises(EdgeValidationError) as incompatible:
        validate_edge_endpoints(edge, from_object=bad_from, to_object=requirement)
    assert incompatible.value.code == DomainErrorCode.EDGE_TYPE_INCOMPATIBLE

    cross = GovernanceObject(
        object_id=ids.requirement_object,
        tenant_id=ids.tenant_beta,
        object_type="Requirement",
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    with pytest.raises(CrossTenantAccessError):
        validate_edge_endpoints(edge, from_object=evidence, to_object=cross)


def test_requirement_evidence_and_approval_records() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    requirement = RequirementRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=ids.requirement_object,
        revision=1,
        mission_object_id=ids.mission_object,
        statement="Must isolate tenants",
        created_at=now,
        created_by_actor_id=ids.human_owner,
        content_hash="sha256:req",
    )
    evidence = EvidenceRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=generate_uuidv7(),
        revision=1,
        requirement_object_id=requirement.object_id,
        artifact_object_id=generate_uuidv7(),
        content_hash="sha256:ev",
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    approval = ApprovalRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=generate_uuidv7(),
        revision=1,
        subject_object_id=ids.mission_object,
        subject_revision=3,
        created_at=now,
        created_by_actor_id=ids.human_reviewer,
        content_hash="sha256:appr",
    )
    assert evidence.requirement_object_id == requirement.object_id
    assert approval.subject_revision == 3


def test_edge_persist_rejects_dangling_incompatible_and_cross_tenant() -> None:
    import sqlite3

    from holodeck_governance.storage.sqlite.edges import SqliteEdgeRepository
    from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
    from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
    from holodeck_governance.domain.revisions import ObjectRevision, content_hash_for

    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
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
        (ids.tenant_beta, now.isoformat(), ids.system_service),
    )
    revisions = SqliteRevisionRepository(conn)
    edges = SqliteEdgeRepository(conn)

    def register(object_id: str, tenant_id: str, object_type: str) -> None:
        revisions.register_object(
            GovernanceObject(
                object_id=object_id,
                tenant_id=tenant_id,
                object_type=object_type,
                created_at=now,
                created_by_actor_id=ids.human_owner,
            )
        )
        rev = ObjectRevision(
            revision_id=generate_uuidv7(),
            tenant_id=tenant_id,
            object_id=object_id,
            revision=1,
            content_hash=content_hash_for({"t": object_type}),
            payload={"t": object_type},
            created_at=now,
            created_by_actor_id=ids.human_owner,
            finalized=True,
        )
        revisions._insert_revision(rev)
        revisions._upsert_head(rev)

    evidence_id = generate_uuidv7()
    requirement_id = ids.requirement_object
    register(evidence_id, ids.tenant_alpha, "Evidence")
    register(requirement_id, ids.tenant_alpha, "Requirement")

    ok = TraceabilityEdge(
        edge_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        edge_type="evidence_supports_requirement",
        from_object_id=evidence_id,
        from_revision=1,
        to_object_id=requirement_id,
        to_revision=1,
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    edges.save(ok)

    dangling = TraceabilityEdge(
        edge_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        edge_type="evidence_supports_requirement",
        from_object_id=generate_uuidv7(),
        from_revision=1,
        to_object_id=requirement_id,
        to_revision=1,
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    with pytest.raises(EdgeValidationError) as missing:
        edges.save(dangling)
    assert missing.value.code == DomainErrorCode.EDGE_ENDPOINT_MISSING

    mission_id = generate_uuidv7()
    register(mission_id, ids.tenant_alpha, "Mission")
    incompatible = TraceabilityEdge(
        edge_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        edge_type="evidence_supports_requirement",
        from_object_id=mission_id,
        from_revision=1,
        to_object_id=requirement_id,
        to_revision=1,
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    with pytest.raises(EdgeValidationError) as bad_type:
        edges.save(incompatible)
    assert bad_type.value.code == DomainErrorCode.EDGE_TYPE_INCOMPATIBLE

    beta_req = generate_uuidv7()
    register(beta_req, ids.tenant_beta, "Requirement")
    cross = TraceabilityEdge(
        edge_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        edge_type="evidence_supports_requirement",
        from_object_id=evidence_id,
        from_revision=1,
        to_object_id=beta_req,
        to_revision=1,
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    with pytest.raises(CrossTenantAccessError):
        edges.save(cross)


def test_record_family_write_repos_persist_and_reload() -> None:
    import sqlite3

    from holodeck_governance.domain.records.artifact import ArtifactRecord
    from holodeck_governance.domain.records.decision import DecisionRecord
    from holodeck_governance.domain.records.run import RunRecord
    from holodeck_governance.domain.records.test_plan import TestPlanRecord
    from holodeck_governance.storage.sqlite.records import SqliteRecordRepository
    from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
    from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
    from holodeck_governance.domain.revisions import ObjectRevision, content_hash_for

    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    revisions = SqliteRevisionRepository(conn)
    task_object_id = generate_uuidv7()
    for object_id, object_type in (
        (ids.mission_object, "Mission"),
        (task_object_id, "Task"),
    ):
        revisions.register_object(
            GovernanceObject(
                object_id=object_id,
                tenant_id=ids.tenant_alpha,
                object_type=object_type,
                created_at=now,
                created_by_actor_id=ids.human_owner,
            )
        )
        rev = ObjectRevision(
            revision_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=object_id,
            revision=1,
            content_hash=content_hash_for({"t": object_type}),
            payload={"t": object_type},
            created_at=now,
            created_by_actor_id=ids.human_owner,
            finalized=True,
        )
        revisions._insert_revision(rev)
        revisions._upsert_head(rev)

    repo = SqliteRecordRepository(conn)
    requirement = repo.save_requirement(
        RequirementRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=ids.requirement_object,
            revision=1,
            mission_object_id=ids.mission_object,
            statement="Isolate tenants",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    loaded = repo.get_requirement(requirement.object_id, 1)
    assert loaded is not None
    assert loaded.statement == "Isolate tenants"

    artifact_id = generate_uuidv7()
    repo.save_artifact(
        ArtifactRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=artifact_id,
            revision=1,
            locator="artifact://blob",
            content_hash="sha256:art",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    evidence_id = generate_uuidv7()
    repo.save_evidence(
        EvidenceRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=evidence_id,
            revision=1,
            requirement_object_id=requirement.object_id,
            artifact_object_id=artifact_id,
            content_hash="sha256:ev",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    repo.save_test_plan(
        TestPlanRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=generate_uuidv7(),
            revision=1,
            mission_object_id=ids.mission_object,
            summary="Cover GS paths",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    repo.save_run(
        RunRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=generate_uuidv7(),
            revision=1,
            task_object_id=task_object_id,
            mission_object_id=ids.mission_object,
            state="active",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    repo.save_decision(
        DecisionRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=generate_uuidv7(),
            revision=1,
            subject_object_id=ids.mission_object,
            subject_revision=1,
            outcome="accepted",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    assert conn.execute("SELECT COUNT(*) FROM gov_requirements").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_evidence").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_decisions").fetchone()[0] == 1
    from holodeck_governance.domain.records.review import EscalationRecord

    repo.save_escalation(
        EscalationRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=generate_uuidv7(),
            revision=1,
            subject_object_id=ids.mission_object,
            trigger="outbox_dead_letter",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    assert conn.execute("SELECT COUNT(*) FROM gov_escalations").fetchone()[0] == 1
