"""M2-025 bounded factual code-graph queries."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from holodeck_governance.adapters.code_graph.python_ast import PythonStdlibAstExtractor
from holodeck_governance.application.code_graph_ingestion import (
    CodeGraphIngestionService,
    GraphBuildRequest,
)
from holodeck_governance.application.code_graph_queries import (
    CodeGraphQueryService,
    GraphQueryScope,
)
from holodeck_governance.application.collaboration import (
    CollaborationApplicationService,
)
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.assignments import RoleAssignment
from holodeck_governance.domain.authority.roles import RoleProfile
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    MalformedCommandError,
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
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    EntityKind,
    ExtractionLimits,
    QueryBudget,
    SnapshotStatus,
    TraversalDirection,
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

from python_reference import (  # noqa: E402
    REVISIONS_PATH,
    TREES_ROOT,
    fixture_revision_id,
)

NOW = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)
REV_A = fixture_revision_id("rev_a")
REV_B = fixture_revision_id("rev_b")
LIMITS = ExtractionLimits(max_files=200, max_entities=5000, max_relations=20000)
BUDGET = QueryBudget(max_depth=4, max_results=200, max_visited_nodes=500)


def _changed_paths_rev_b() -> tuple[str, ...]:
    payload = json.loads(REVISIONS_PATH.read_text(encoding="utf-8"))
    return tuple(payload["revisions"]["rev_b"]["changed_paths_from_rev_a"])


def _harness() -> tuple[
    sqlite3.Connection,
    CodeGraphIngestionService,
    CodeGraphQueryService,
    FixtureIds,
    str,
    SqliteCodeGraphRepository,
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

    intelligence = SqliteWorkspaceIntelligenceRepository(conn)
    graphs = SqliteCodeGraphRepository(conn)
    ingestion = CodeGraphIngestionService(
        collaboration=collab,
        intelligence=intelligence,
        graphs=graphs,
        extractor=PythonStdlibAstExtractor(),
        events=SqliteDomainEventRepository(conn),
        receipts=SqliteCommandReceiptRepository(conn),
        commit=conn.commit,
    )
    queries = CodeGraphQueryService(
        collaboration=collab,
        intelligence=intelligence,
        graphs=graphs,
    )
    return conn, ingestion, queries, ids, binding.binding_id, graphs


def _scope(ids: FixtureIds, binding_id: str, *, snapshot_id: str | None = None) -> GraphQueryScope:
    return GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        snapshot_id=snapshot_id,
    )


def _build_rev_a(
    ingestion: CodeGraphIngestionService,
    ids: FixtureIds,
    binding_id: str,
    *,
    idempotency_key: str = "rev-a",
) -> object:
    return ingestion.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / "rev_a",
            requested_revision=REV_A,
            actor_id=ids.human_owner,
            idempotency_key=idempotency_key,
            limits=LIMITS,
            at=NOW,
        )
    )


def _build_rev_b(
    ingestion: CodeGraphIngestionService,
    ids: FixtureIds,
    binding_id: str,
    *,
    idempotency_key: str = "rev-b",
    base_snapshot_id: str | None = None,
) -> object:
    return ingestion.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / "rev_b",
            requested_revision=REV_B,
            actor_id=ids.human_owner,
            idempotency_key=idempotency_key,
            limits=LIMITS,
            at=NOW,
            base_snapshot_id=base_snapshot_id,
            changed_paths=_changed_paths_rev_b() if base_snapshot_id else (),
        )
    )


def test_find_entities_by_path_and_kind_returns_greeter_and_api_entries() -> None:
    _conn, ingestion, queries, ids, binding_id, _graphs = _harness()
    built = _build_rev_a(ingestion, ids, binding_id)
    assert built.status is SnapshotStatus.ACTIVE
    scope = _scope(ids, binding_id)

    by_path = queries.find_entities(
        scope,
        path="sample_app/service.py",
        entity_kinds=(EntityKind.CLASS,),
        budget=BUDGET,
    )
    assert any(
        entity.qualified_name == "sample_app.service.Greeter"
        for entity in by_path.entities
    )
    assert by_path.coverage.coverage_status.value == "complete"
    assert by_path.entities == tuple(
        sorted(by_path.entities, key=lambda entity: entity.entity_key)
    )

    api = queries.find_entities(
        scope,
        entity_kinds=(EntityKind.API_ENTRY_POINT,),
        budget=BUDGET,
    )
    assert api.entities
    assert all(entity.entity_kind is EntityKind.API_ENTRY_POINT for entity in api.entities)
    assert any(
        entity.qualified_name == "sample_app.api.handle_greet" for entity in api.entities
    )


def test_neighbors_deterministic_and_traverse_respects_budgets() -> None:
    _conn, ingestion, queries, ids, binding_id, _graphs = _harness()
    _build_rev_a(ingestion, ids, binding_id)
    scope = _scope(ids, binding_id)
    greeter = queries.find_entities(
        scope,
        path="sample_app/service.py",
        entity_kinds=(EntityKind.CLASS,),
        qualified_name="Greeter",
        budget=BUDGET,
    ).entities[0]

    first = queries.get_neighbors(
        scope,
        greeter.entity_fact_id,
        direction=TraversalDirection.BOTH,
        budget=BUDGET,
    )
    second = queries.get_neighbors(
        scope,
        greeter.entity_fact_id,
        direction=TraversalDirection.BOTH,
        budget=BUDGET,
    )
    assert first.neighbors
    assert [hit.neighbor.entity_key for hit in first.neighbors] == [
        hit.neighbor.entity_key for hit in second.neighbors
    ]
    assert [hit.relation.relation_fact_id for hit in first.neighbors] == [
        hit.relation.relation_fact_id for hit in second.neighbors
    ]

    deep = queries.traverse_paths(
        scope,
        greeter.entity_fact_id,
        direction=TraversalDirection.OUTGOING,
        budget=QueryBudget(max_depth=1, max_results=50, max_visited_nodes=50),
    )
    assert "max_depth" in deep.omissions.reasons or all(
        len(path.steps) <= 2 for path in deep.paths
    )

    limited = queries.traverse_paths(
        scope,
        greeter.entity_fact_id,
        direction=TraversalDirection.OUTGOING,
        budget=QueryBudget(max_depth=4, max_results=1, max_visited_nodes=50),
    )
    assert len(limited.paths) <= 1
    assert "max_results" in limited.omissions.reasons

    visited = queries.traverse_paths(
        scope,
        greeter.entity_fact_id,
        direction=TraversalDirection.OUTGOING,
        budget=QueryBudget(max_depth=4, max_results=50, max_visited_nodes=2),
    )
    assert "max_visited_nodes" in visited.omissions.reasons


def test_change_neighborhood_includes_service_paths() -> None:
    _conn, ingestion, queries, ids, binding_id, _graphs = _harness()
    _build_rev_a(ingestion, ids, binding_id)
    scope = _scope(ids, binding_id)
    changed = _changed_paths_rev_b()
    result = queries.get_change_neighborhood(scope, changed, budget=BUDGET)
    assert "sample_app/service.py" in result.reextract_paths
    assert any(
        entity.repository_relative_path == "sample_app/service.py"
        for entity in result.entities
    )
    assert result.fallback_full is False


def test_compare_snapshots_rev_a_vs_rev_b_shows_diffs() -> None:
    _conn, ingestion, queries, ids, binding_id, _graphs = _harness()
    rev_a = _build_rev_a(ingestion, ids, binding_id)
    rev_b = _build_rev_b(ingestion, ids, binding_id, idempotency_key="rev-b-full")
    assert rev_a.status is SnapshotStatus.ACTIVE or rev_a.snapshot_id
    assert rev_b.status is SnapshotStatus.ACTIVE
    scope = _scope(ids, binding_id)
    comparison = queries.compare_snapshots(
        scope, rev_a.snapshot_id, rev_b.snapshot_id
    )
    assert comparison.comparison.only_left_entities + comparison.comparison.only_right_entities > 0 or (
        comparison.comparison.only_left_relations
        + comparison.comparison.only_right_relations
        > 0
    )


def test_get_sources_for_facts_returns_observation_ids() -> None:
    _conn, ingestion, queries, ids, binding_id, _graphs = _harness()
    _build_rev_a(ingestion, ids, binding_id)
    scope = _scope(ids, binding_id)
    entities = queries.find_entities(
        scope,
        path="sample_app/service.py",
        entity_kinds=(EntityKind.CLASS,),
        budget=BUDGET,
    ).entities
    assert entities
    sources = queries.get_sources_for_facts(
        scope, entity_fact_ids=(entities[0].entity_fact_id,)
    )
    assert sources.provenance
    assert sources.provenance[0].observation_id
    assert sources.provenance[0].source_id


def test_cross_tenant_and_wrong_workspace_fail() -> None:
    conn, ingestion, queries, ids, binding_id, _graphs = _harness()
    _build_rev_a(ingestion, ids, binding_id)

    with pytest.raises(CrossTenantAccessError):
        queries.find_entities(
            GraphQueryScope(
                tenant_id=ids.tenant_beta,
                workspace_object_id=ids.workspace_alpha_1,
                repository_binding_id=binding_id,
            ),
            budget=BUDGET,
        )

    other_workspace = generate_uuidv7()
    SqliteRevisionRepository(conn).register_object(
        GovernanceObject(
            object_id=other_workspace,
            tenant_id=ids.tenant_alpha,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    with pytest.raises((MalformedCommandError, NotFoundGovernanceError)):
        queries.find_entities(
            GraphQueryScope(
                tenant_id=ids.tenant_alpha,
                workspace_object_id=other_workspace,
                repository_binding_id=binding_id,
            ),
            budget=BUDGET,
        )


def test_historical_get_snapshot_after_supersede() -> None:
    _conn, ingestion, queries, ids, binding_id, graphs = _harness()
    rev_a = _build_rev_a(ingestion, ids, binding_id)
    first_id = rev_a.snapshot_id
    _build_rev_b(ingestion, ids, binding_id, idempotency_key="rev-b-hist")
    active = queries.get_active_snapshot(_scope(ids, binding_id))
    assert active.snapshot_id != first_id
    historical = queries.get_snapshot(
        _scope(ids, binding_id, snapshot_id=first_id)
    )
    assert historical.snapshot_id == first_id
    assert historical.status is SnapshotStatus.SUPERSEDED
    stored = graphs.require_snapshot(first_id, tenant_id=ids.tenant_alpha)
    assert stored.repository_revision == REV_A
    entities = queries.find_entities(
        _scope(ids, binding_id, snapshot_id=first_id),
        entity_kinds=(EntityKind.CLASS,),
        path="sample_app/service.py",
        budget=BUDGET,
    )
    assert any(
        entity.qualified_name == "sample_app.service.Greeter"
        for entity in entities.entities
    )
