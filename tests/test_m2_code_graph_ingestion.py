"""M2-023 governed code-graph ingestion and activation."""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from holodeck_governance.adapters.code_graph.python_ast import PythonStdlibAstExtractor
from holodeck_governance.application.code_graph_ingestion import (
    CodeGraphIngestionService,
    GraphBuildRequest,
)
from holodeck_governance.application.collaboration import (
    CollaborationApplicationService,
)
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.assignments import RoleAssignment
from holodeck_governance.domain.authority.roles import RoleProfile
from holodeck_governance.domain.errors import (
    IdempotencyConflictError,
    MissingAuthorityError,
    NotFoundGovernanceError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace import (
    RepositoryBinding,
    WorkspaceBindingStatus,
)
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    M2_EVENT_CODE_GRAPH_BUILD_COMPLETED,
    M2_EVENT_CODE_GRAPH_BUILD_FAILED,
    M2_EVENT_CODE_GRAPH_BUILD_PARTIAL,
    M2_EVENT_CODE_GRAPH_BUILD_REQUESTED,
    M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    ExtractionLimits,
    SnapshotStatus,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.code_graph import SqliteCodeGraphRepository
from holodeck_governance.storage.sqlite.collaboration import (
    SqliteCollaborationRepository,
)
from holodeck_governance.storage.sqlite.intelligence import (
    SqliteWorkspaceIntelligenceRepository,
)
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_PARENT = ROOT / "tests" / "fixtures" / "code_graph"
if str(_FIXTURE_PARENT) not in sys.path:
    sys.path.insert(0, str(_FIXTURE_PARENT))

from python_reference import TREES_ROOT, fixture_revision_id  # noqa: E402

NOW = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)
REV_A = fixture_revision_id("rev_a")


def _service() -> tuple[
    sqlite3.Connection,
    CodeGraphIngestionService,
    FixtureIds,
    str,
]:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    migrate_governance(conn)
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    auth = SqliteAuthorityRepository(conn)
    for actor_id, name, kind in (
        (ids.human_owner, "Owner", ActorKind.HUMAN),
        (ids.system_service, "System", ActorKind.SERVICE),
        (ids.human_reviewer, "Reviewer", ActorKind.HUMAN),
    ):
        auth.save_actor(
            Actor(
                actor_id=actor_id,
                tenant_id=ids.tenant_alpha,
                kind=kind,
                display_name=name,
                created_at=FIXED_CLOCK,
                created_by_actor_id=ids.system_service,
            )
        )
    revisions = SqliteRevisionRepository(conn)
    revisions.register_object(
        GovernanceObject(
            object_id=ids.workspace_alpha_1,
            tenant_id=ids.tenant_alpha,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
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
            name="intelligence-curator",
            permissions=(INTELLIGENCE_CURATE_PERMISSION,),
            jurisdiction={"tenant": ids.tenant_alpha},
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_assignment(
        RoleAssignment(
            assignment_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            actor_id=ids.human_owner,
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
    collab = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )
    ref = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="git",
        object_type="repository",
        external_object_id="repo-1",
        locator="git://example/repo",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    collab.save_external_reference(ref)
    binding = RepositoryBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        provider="git",
        external_repository_id="repo-1",
        canonical_locator="git://example/repo",
        default_branch="main",
        status=WorkspaceBindingStatus.ACTIVE,
        external_reference_id=ref.reference_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    collab.save_repository_binding(binding)
    from holodeck_governance.storage.sqlite.repos import (
        SqliteCommandReceiptRepository,
        SqliteDomainEventRepository,
    )

    service = CodeGraphIngestionService(
        collaboration=collab,
        intelligence=SqliteWorkspaceIntelligenceRepository(conn),
        graphs=SqliteCodeGraphRepository(conn),
        extractor=PythonStdlibAstExtractor(),
        events=SqliteDomainEventRepository(conn),
        receipts=SqliteCommandReceiptRepository(conn),
        commit=conn.commit,
    )
    return conn, service, ids, binding.binding_id


def _request(
    ids: FixtureIds,
    binding_id: str,
    *,
    idempotency_key: str = "graph-build-1",
    revision: str = REV_A,
    actor_id: str | None = None,
    expected_active_snapshot_id: str | None = None,
    expect_no_active_snapshot: bool = True,
) -> GraphBuildRequest:
    return GraphBuildRequest(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_path=TREES_ROOT / "rev_a",
        requested_revision=revision,
        actor_id=actor_id or ids.human_owner,
        idempotency_key=idempotency_key,
        limits=ExtractionLimits(max_files=200, max_entities=5000, max_relations=20000),
        at=NOW,
        expected_active_snapshot_id=expected_active_snapshot_id,
        expect_no_active_snapshot=expect_no_active_snapshot,
    )


def test_fixture_revision_builds_active_snapshot_with_events() -> None:
    conn, service, ids, binding_id = _service()
    result = service.build_graph(_request(ids, binding_id))
    assert result.status is SnapshotStatus.ACTIVE
    assert result.replayed is False
    assert result.entity_count > 0
    assert result.relation_count > 0
    assert result.actual_revision == REV_A
    assert M2_EVENT_CODE_GRAPH_BUILD_REQUESTED in result.event_types
    assert (
        M2_EVENT_CODE_GRAPH_BUILD_COMPLETED in result.event_types
        or M2_EVENT_CODE_GRAPH_BUILD_PARTIAL in result.event_types
    )
    assert M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED in result.event_types

    status = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert status.active_snapshot is not None
    assert status.active_snapshot.snapshot_id == result.snapshot_id
    assert status.active_run is not None
    assert status.active_run.requested_revision == status.active_run.actual_revision

    entities = SqliteCodeGraphRepository(conn).list_snapshot_entities(
        result.snapshot_id, tenant_id=ids.tenant_alpha
    )
    assert entities
    assert all(e.source_observation_id for e in entities)

    event_types = {
        str(row["event_type"])
        for row in conn.execute(
            "SELECT event_type FROM gov_domain_events WHERE tenant_id = ?",
            (ids.tenant_alpha,),
        )
    }
    assert M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED in event_types


def test_idempotent_replay_returns_original_result() -> None:
    _conn, service, ids, binding_id = _service()
    first = service.build_graph(_request(ids, binding_id, idempotency_key="same-key"))
    second = service.build_graph(_request(ids, binding_id, idempotency_key="same-key"))
    assert second.replayed is True
    assert first.replayed is False
    assert second == replace(first, replayed=True)


def test_conflicting_idempotency_key_is_rejected() -> None:
    _conn, service, ids, binding_id = _service()
    service.build_graph(_request(ids, binding_id, idempotency_key="conflict"))
    with pytest.raises(IdempotencyConflictError):
        service.build_graph(
            _request(
                ids,
                binding_id,
                idempotency_key="conflict",
                revision="fixture:" + ("ab" * 32),
            )
        )


def test_missing_authority_is_rejected() -> None:
    _conn, service, ids, binding_id = _service()
    with pytest.raises(MissingAuthorityError):
        service.build_graph(_request(ids, binding_id, actor_id=ids.human_reviewer))


def test_unknown_binding_is_rejected() -> None:
    _conn, service, ids, _binding_id = _service()
    with pytest.raises(NotFoundGovernanceError):
        service.build_graph(_request(ids, "01900000-0000-7000-8000-00000000dead"))


def test_extraction_failure_emits_failed_event_without_active_snapshot() -> None:
    conn, service, ids, binding_id = _service()
    result = service.build_graph(
        _request(ids, binding_id, revision="fixture:" + ("cd" * 32))
    )
    assert result.status is SnapshotStatus.FAILED
    assert M2_EVENT_CODE_GRAPH_BUILD_FAILED in result.event_types
    status = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert status.active_snapshot is None
    assert (
        conn.execute(
            "SELECT COUNT(*) AS n FROM gov_code_graph_snapshots WHERE status = 'active'"
        ).fetchone()["n"]
        == 0
    )


def test_second_revision_rebuild_succeeds_with_stable_sources() -> None:
    conn, service, ids, binding_id = _service()
    rev_b = fixture_revision_id("rev_b")
    first = service.build_graph(
        _request(ids, binding_id, idempotency_key="rev-a", revision=REV_A)
    )
    assert first.status is SnapshotStatus.ACTIVE
    second = service.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / "rev_b",
            requested_revision=rev_b,
            actor_id=ids.human_owner,
            idempotency_key="rev-b",
            limits=ExtractionLimits(
                max_files=200, max_entities=5000, max_relations=20000
            ),
            at=NOW,
            expected_active_snapshot_id=first.snapshot_id,
            expect_no_active_snapshot=False,
        )
    )
    assert second.status is SnapshotStatus.ACTIVE
    assert second.actual_revision == rev_b
    assert second.snapshot_id != first.snapshot_id
    status = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert status.active_snapshot is not None
    assert status.active_snapshot.snapshot_id == second.snapshot_id
    superseded = conn.execute(
        """
        SELECT COUNT(*) AS n FROM gov_code_graph_snapshots
        WHERE snapshot_id = ? AND status = 'superseded'
        """,
        (first.snapshot_id,),
    ).fetchone()["n"]
    assert superseded == 1
    # Same path keeps one source_id across revisions; observations differ.
    locators = conn.execute(
        """
        SELECT locator, COUNT(DISTINCT source_id) AS sources
        FROM gov_workspace_sources
        WHERE tenant_id = ? AND workspace_object_id = ?
          AND locator LIKE 'sample_app/%.py'
        GROUP BY locator
        """,
        (ids.tenant_alpha, ids.workspace_alpha_1),
    ).fetchall()
    assert locators
    assert all(int(row["sources"]) == 1 for row in locators)


def test_partial_build_never_activates_without_a_durable_policy_seam() -> None:
    _conn, service, ids, binding_id = _service()
    rejected = service.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / "rev_a",
            requested_revision=REV_A,
            actor_id=ids.human_owner,
            idempotency_key="partial-default",
            limits=ExtractionLimits(max_files=1, max_entities=5000),
            at=NOW,
            expect_no_active_snapshot=True,
        )
    )
    assert rejected.status is SnapshotStatus.FAILED
    status = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert status.active_snapshot is None
