"""M2-023 failure recovery: failed rebuild leaves prior active unchanged."""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace import (
    RepositoryBinding,
    WorkspaceBindingStatus,
)
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    M2_EVENT_CODE_GRAPH_BUILD_FAILED,
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

NOW = datetime(2026, 7, 29, 16, 30, tzinfo=UTC)
REV_A = fixture_revision_id("rev_a")


class _FailingExtractor:
    """Extractor that raises after describe_capabilities for rebuild failure tests."""

    def __init__(self, inner: PythonStdlibAstExtractor, *, fail: bool = False) -> None:
        self._inner = inner
        self.fail = fail

    def describe_capabilities(self):
        return self._inner.describe_capabilities()

    def extract(self, request):
        if self.fail:
            raise RuntimeError("simulated extractor crash")
        return self._inner.extract(request)


def _world() -> tuple[
    sqlite3.Connection,
    CodeGraphIngestionService,
    _FailingExtractor,
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

    extractor = _FailingExtractor(PythonStdlibAstExtractor())
    service = CodeGraphIngestionService(
        collaboration=collab,
        intelligence=SqliteWorkspaceIntelligenceRepository(conn),
        graphs=SqliteCodeGraphRepository(conn),
        extractor=extractor,
        events=SqliteDomainEventRepository(conn),
        receipts=SqliteCommandReceiptRepository(conn),
        commit=conn.commit,
    )
    return conn, service, extractor, ids, binding.binding_id


def test_failed_rebuild_preserves_prior_active_snapshot() -> None:
    conn, service, extractor, ids, binding_id = _world()
    first = service.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / "rev_a",
            requested_revision=REV_A,
            actor_id=ids.human_owner,
            idempotency_key="build-success",
            limits=ExtractionLimits(max_files=200, max_entities=5000),
            at=NOW,
            expect_no_active_snapshot=True,
        )
    )
    assert first.status is SnapshotStatus.ACTIVE

    extractor.fail = True
    failed = service.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / "rev_a",
            requested_revision=REV_A,
            actor_id=ids.human_owner,
            idempotency_key="build-fail",
            limits=ExtractionLimits(max_files=200, max_entities=5000),
            at=NOW,
            expected_active_snapshot_id=first.snapshot_id,
            expect_no_active_snapshot=False,
        )
    )
    assert failed.status is SnapshotStatus.FAILED
    assert M2_EVENT_CODE_GRAPH_BUILD_FAILED in failed.event_types

    status = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert status.active_snapshot is not None
    assert status.active_snapshot.snapshot_id == first.snapshot_id
    assert status.active_snapshot.status is SnapshotStatus.ACTIVE

    active_count = conn.execute(
        """
        SELECT COUNT(*) AS n FROM gov_code_graph_snapshots
        WHERE tenant_id = ? AND repository_binding_id = ? AND status = 'active'
        """,
        (ids.tenant_alpha, binding_id),
    ).fetchone()["n"]
    assert active_count == 1
