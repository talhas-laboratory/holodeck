"""M2-025 high-recall code-graph sentinels."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    ExtractionLimits,
    QueryBudget,
    SentinelKind,
    SentinelStatus,
    evaluate_sentinels,
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
    return ingestion, queries, ids, binding.binding_id, graphs


def _scope(ids: FixtureIds, binding_id: str) -> GraphQueryScope:
    return GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )


def _build(
    ingestion: CodeGraphIngestionService,
    ids: FixtureIds,
    binding_id: str,
    *,
    tree: str,
    revision: str,
    key: str,
    graphs: object,
) -> object:
    active = graphs.get_active_snapshot(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    return ingestion.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / tree,
            requested_revision=revision,
            actor_id=ids.human_owner,
            idempotency_key=key,
            limits=LIMITS,
            at=NOW,
            expected_active_snapshot_id=(
                None if active is None else active.snapshot_id
            ),
            expect_no_active_snapshot=active is None,
        )
    )


def test_rev_a_and_rev_b_sentinel_goldens_activate_expected_kinds() -> None:
    ingestion, queries, ids, binding_id, graphs = _harness()
    for tree, revision, key in (
        ("rev_a", REV_A, "sent-a"),
        ("rev_b", REV_B, "sent-b"),
    ):
        _build(
            ingestion,
            ids,
            binding_id,
            tree=tree,
            revision=revision,
            key=key,
            graphs=graphs,
        )
        result = queries.evaluate_sentinels(_scope(ids, binding_id), budget=BUDGET)
        kinds = {finding.kind for finding in result.findings}
        assert SentinelKind.API_ENTRY in kinds
        assert SentinelKind.SCHEMA_OR_MIGRATION in kinds
        assert SentinelKind.MANIFEST in kinds
        assert SentinelKind.CONFIGURATION in kinds
        assert SentinelKind.TEST_ASSOCIATION in kinds
        assert all(
            finding.status in (SentinelStatus.ACTIVATED, SentinelStatus.UNRESOLVED)
            for finding in result.findings
        )
        assert all(finding.status.value != "cleared" for finding in result.findings)


def test_change_sentinels_activate_on_service_and_test_paths() -> None:
    ingestion, queries, ids, binding_id, graphs = _harness()
    _build(
        ingestion,
        ids,
        binding_id,
        tree="rev_a",
        revision=REV_A,
        key="chg-a",
        graphs=graphs,
    )
    changed = _changed_paths_rev_b()
    result = queries.evaluate_sentinels(
        _scope(ids, binding_id), changed_paths=changed, budget=BUDGET
    )
    activated = [
        finding
        for finding in result.findings
        if finding.status is SentinelStatus.ACTIVATED
    ]
    assert activated
    path_refs = {path for finding in activated for path in finding.path_refs}
    assert "sample_app/service.py" in path_refs or any(
        path.startswith("tests/") for path in path_refs
    )
    assert any(
        finding.kind in (SentinelKind.PUBLIC_EXPORT, SentinelKind.TEST_ASSOCIATION)
        for finding in activated
    )


def test_sensitive_path_prefix_activates_empty_list_unresolved() -> None:
    ingestion, queries, ids, binding_id, graphs = _harness()
    built = _build(
        ingestion,
        ids,
        binding_id,
        tree="rev_a",
        revision=REV_A,
        key="sens-a",
        graphs=graphs,
    )
    scope = _scope(ids, binding_id)
    empty = queries.evaluate_sentinels(scope, budget=BUDGET)
    sensitive_empty = next(
        finding
        for finding in empty.findings
        if finding.kind is SentinelKind.SENSITIVE_PATH_OR_SYMBOL
    )
    assert sensitive_empty.status is SentinelStatus.UNRESOLVED
    assert sensitive_empty.status.value != "cleared"

    activated = queries.evaluate_sentinels(
        scope, sensitive_path_prefixes=("migrations/",), budget=BUDGET
    )
    sensitive = next(
        finding
        for finding in activated.findings
        if finding.kind is SentinelKind.SENSITIVE_PATH_OR_SYMBOL
    )
    assert sensitive.status is SentinelStatus.ACTIVATED
    assert any(path.startswith("migrations/") for path in sensitive.path_refs)

    # Domain invariant on raw evaluate as well.
    entities = graphs.list_snapshot_entities(
        built.snapshot_id, tenant_id=ids.tenant_alpha
    )
    relations = graphs.list_snapshot_relations(
        built.snapshot_id, tenant_id=ids.tenant_alpha
    )
    snapshot = graphs.require_snapshot(built.snapshot_id, tenant_id=ids.tenant_alpha)
    raw = evaluate_sentinels(
        entities=entities,
        relations=relations,
        coverage_status=snapshot.coverage_status,
        sensitive_path_prefixes=(),
        sensitive_symbols=(),
    )
    assert all(
        finding.status is not getattr(SentinelStatus, "CLEARED", None)
        for finding in raw
    )
    assert all(finding.status.value != "cleared" for finding in raw)


def test_sentinels_never_emit_cleared_status() -> None:
    ingestion, queries, ids, binding_id, graphs = _harness()
    _build(
        ingestion,
        ids,
        binding_id,
        tree="rev_a",
        revision=REV_A,
        key="clr-a",
        graphs=graphs,
    )
    result = queries.evaluate_sentinels(
        _scope(ids, binding_id),
        changed_paths=_changed_paths_rev_b(),
        ownership_tags=(),
        sensitive_path_prefixes=(),
        sensitive_symbols=("Greeter.invoke",),
        budget=BUDGET,
    )
    assert SentinelStatus.__members__.keys() == {"ACTIVATED", "UNRESOLVED"}
    assert all(finding.status.value != "cleared" for finding in result.findings)
    assert "CLEARED" not in SentinelStatus.__members__
