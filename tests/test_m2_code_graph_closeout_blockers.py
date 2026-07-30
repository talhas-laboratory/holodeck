"""M2 closeout review blockers: changed_paths, CAS, impact cap, deletion, readiness."""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from holodeck_governance.adapters.code_graph.python_ast import (
    PythonStdlibAstExtractor,
    stable_source_id,
)
from holodeck_governance.adapters.code_graph.revision import tree_content_hash
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
from holodeck_governance.domain.errors import ContentionError, MalformedCommandError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace import (
    RepositoryBinding,
    WorkspaceBindingStatus,
)
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    ContextModule,
    ModuleApprovalStatus,
    StaleStatus,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    MAX_INCREMENTAL_IMPACT_DEPTH,
    CodeEntityFact,
    CodeRelationFact,
    CoverageStatus,
    EntityKind,
    ExtractionLimits,
    ExtractionRunStatus,
    FactualGraphReadiness,
    ObservationMethod,
    QueryBudget,
    RelationKind,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    SentinelKind,
    SnapshotStatus,
    SourceSpan,
    build_entity_key,
    compare_normalized_snapshots,
    evaluate_factual_graph_readiness,
    evaluate_sentinels,
    plan_incremental_refresh,
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

NOW = datetime(2026, 7, 29, 20, 0, tzinfo=UTC)
REV_A = fixture_revision_id("rev_a")
REV_B = fixture_revision_id("rev_b")
LIMITS = ExtractionLimits(max_files=200, max_entities=5000, max_relations=20000)
BUDGET = QueryBudget(max_depth=4, max_results=200, max_visited_nodes=500)


def _changed_paths_rev_b() -> tuple[str, ...]:
    payload = json.loads(REVISIONS_PATH.read_text(encoding="utf-8"))
    return tuple(payload["revisions"]["rev_b"]["changed_paths_from_rev_a"])


def _service(
    *,
    extractor=None,
) -> tuple[
    sqlite3.Connection,
    CodeGraphIngestionService,
    FixtureIds,
    str,
    SqliteWorkspaceIntelligenceRepository,
    SqliteCodeGraphRepository,
    CodeGraphQueryService,
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
        external_object_id="repo-closeout",
        locator="git://example/closeout",
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
        external_repository_id="repo-closeout",
        canonical_locator="git://example/closeout",
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
        extractor=extractor or PythonStdlibAstExtractor(),
        events=SqliteDomainEventRepository(conn),
        receipts=SqliteCommandReceiptRepository(conn),
        commit=conn.commit,
    )
    queries = CodeGraphQueryService(
        collaboration=collab,
        intelligence=intelligence,
        graphs=graphs,
    )
    return conn, ingestion, ids, binding.binding_id, intelligence, graphs, queries


def _build(
    service: CodeGraphIngestionService,
    ids: FixtureIds,
    binding_id: str,
    *,
    revision: str,
    tree: str | Path,
    idempotency_key: str,
    graphs: object,
    base_snapshot_id: str | None = None,
    changed_paths: tuple[str, ...] = (),
    path_includes: tuple[str, ...] = (),
    expected_active_snapshot_id: str | None = None,
    expect_no_active_snapshot: bool | None = None,
) -> object:
    path = Path(tree) if isinstance(tree, Path) else TREES_ROOT / tree
    if expect_no_active_snapshot is None and expected_active_snapshot_id is None:
        if base_snapshot_id is not None:
            # Incremental/replacement CAS names the claimed base, not whatever is
            # currently active — stale bases must fail closed.
            expected_active_snapshot_id = base_snapshot_id
            expect_no_active_snapshot = False
        else:
            active = graphs.get_active_snapshot(
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_alpha_1,
                repository_binding_id=binding_id,
            )
            if active is None:
                expect_no_active_snapshot = True
            else:
                expected_active_snapshot_id = active.snapshot_id
                expect_no_active_snapshot = False
    elif expect_no_active_snapshot is None:
        expect_no_active_snapshot = False
    return service.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=path,
            requested_revision=revision,
            actor_id=ids.human_owner,
            idempotency_key=idempotency_key,
            limits=LIMITS,
            at=NOW,
            base_snapshot_id=base_snapshot_id,
            expected_active_snapshot_id=expected_active_snapshot_id,
            expect_no_active_snapshot=bool(expect_no_active_snapshot),
            changed_paths=changed_paths,
            path_includes=path_includes,
        )
    )


def _entity(
    *,
    path: str,
    kind: EntityKind = EntityKind.FILE,
    fact_id: str | None = None,
    qualified_name: str | None = None,
) -> CodeEntityFact:
    eid = fact_id or generate_uuidv7()
    qn = qualified_name if qualified_name is not None else path
    return CodeEntityFact(
        entity_fact_id=eid,
        tenant_id="01900000-0000-7000-8000-000000000001",
        workspace_object_id="01900000-0000-7000-8000-000000000002",
        repository_binding_id="01900000-0000-7000-8000-000000000003",
        entity_key=build_entity_key(
            entity_kind=kind, repository_relative_path=path, qualified_name=qn
        ),
        entity_kind=kind,
        repository_relative_path=path,
        source_id=generate_uuidv7(),
        source_observation_id=generate_uuidv7(),
        observation_method=ObservationMethod.DIRECT_PARSE,
        created_at=NOW,
        language="python",
        qualified_name=qn,
    )


def _relation(
    *,
    kind: RelationKind,
    source: CodeEntityFact,
    target: CodeEntityFact,
) -> CodeRelationFact:
    return CodeRelationFact(
        relation_fact_id=generate_uuidv7(),
        tenant_id=source.tenant_id,
        workspace_object_id=source.workspace_object_id,
        repository_binding_id=source.repository_binding_id,
        relation_kind=kind,
        source_entity_fact_id=source.entity_fact_id,
        target_entity_fact_id=target.entity_fact_id,
        evidence_source_id=source.source_id,
        evidence_observation_id=source.source_observation_id,
        observation_method=ObservationMethod.DIRECT_PARSE,
        created_at=NOW,
        evidence_span=SourceSpan(start_line=1, end_line=1),
    )


# --- P0: changed_paths must not restrict full extraction ---


def test_full_build_with_changed_paths_and_no_base_rejected() -> None:
    with pytest.raises(
        MalformedCommandError, match="changed_paths require base_snapshot_id"
    ):
        GraphBuildRequest(
            tenant_id="01900000-0000-7000-8000-000000000001",
            workspace_object_id="01900000-0000-7000-8000-000000000002",
            repository_binding_id="01900000-0000-7000-8000-000000000003",
            repository_path=TREES_ROOT / "rev_a",
            requested_revision=REV_A,
            actor_id="01900000-0000-7000-8000-000000000004",
            idempotency_key="bad",
            limits=LIMITS,
            at=NOW,
            expect_no_active_snapshot=True,
            changed_paths=("sample_app/service.py",),
        )


def test_fallback_full_extract_equals_standalone_full_on_golden() -> None:
    _conn, service, ids, binding_id, _intel, graphs, _queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="p0-a",
    )
    # Force fallback by empty changed_paths with base (still allowed).
    fallback = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="p0-fallback",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=(),
    )
    assert fallback.fallback_full is True
    assert fallback.status is SnapshotStatus.ACTIVE

    # Standalone full rebuild of rev_b on a fresh binding world would be another
    # service; compare against a second full build with no base on new key after
    # resetting active via a fresh service is heavy — instead rebuild full with
    # no base is rejected once active exists only by CAS when base set. Build
    # full with no base on a second service instance.
    _conn2, service2, ids2, binding_id2, _i2, graphs2, _q2 = _service()
    standalone = _build(
        service2,
        ids2,
        binding_id2,
        graphs=graphs2,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="p0-standalone",
    )
    left_e = graphs.list_snapshot_entities(
        fallback.snapshot_id, tenant_id=ids.tenant_alpha
    )
    left_r = graphs.list_snapshot_relations(
        fallback.snapshot_id, tenant_id=ids.tenant_alpha
    )
    right_e = graphs2.list_snapshot_entities(
        standalone.snapshot_id, tenant_id=ids2.tenant_alpha
    )
    right_r = graphs2.list_snapshot_relations(
        standalone.snapshot_id, tenant_id=ids2.tenant_alpha
    )
    # Fingerprints include tenant/workspace ids — compare by entity_key / relation
    # structure via normalized helper after remapping is not available; use counts
    # and entity_key sets (entity_key is path/kind scoped, not tenant-scoped).
    left_keys = {e.entity_key for e in left_e}
    right_keys = {e.entity_key for e in right_e}
    assert left_keys == right_keys
    assert len(left_r) == len(right_r)
    cmp = compare_normalized_snapshots(left_e, left_r, right_e, right_r)
    assert cmp.only_left_entities == 0
    assert cmp.only_right_entities == 0
    assert cmp.only_left_relations == 0
    assert cmp.only_right_relations == 0


# --- P1: CAS activation ---


def test_cas_activation_a_to_b_ok_then_stale_a_fails() -> None:
    _conn, service, ids, binding_id, _intel, graphs, _queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="cas-a",
    )
    assert rev_a.status is SnapshotStatus.ACTIVE
    rev_b = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="cas-b",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    assert rev_b.status is SnapshotStatus.ACTIVE
    active = graphs.get_active_snapshot(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert active is not None
    assert active.snapshot_id == rev_b.snapshot_id

    stale = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="cas-stale-a",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    assert stale.status is SnapshotStatus.FAILED
    assert "base_snapshot_not_current" in stale.coverage_notes
    active_after = graphs.get_active_snapshot(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert active_after is not None
    assert active_after.snapshot_id == rev_b.snapshot_id


def test_cas_two_same_base_race_one_active() -> None:
    _conn, service, ids, binding_id, _intel, graphs, _queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="race-a",
    )
    first = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="race-b1",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    second = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="race-b2",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    assert first.status is SnapshotStatus.ACTIVE
    assert second.status is SnapshotStatus.FAILED
    actives = [
        row
        for row in _conn.execute(
            """
            SELECT snapshot_id FROM gov_code_graph_snapshots
            WHERE repository_binding_id = ? AND status = ?
            """,
            (binding_id, SnapshotStatus.ACTIVE.value),
        ).fetchall()
    ]
    assert len(actives) == 1
    assert actives[0]["snapshot_id"] == first.snapshot_id


def test_activate_snapshot_cas_raises_contention_directly() -> None:
    _conn, service, ids, binding_id, _intel, graphs, _queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="direct-a",
    )
    # Persist a building snapshot manually and try CAS against wrong expected.
    run_id = generate_uuidv7()
    snap_id = generate_uuidv7()
    entity = _entity(path="x.py")
    # Need real FK-compatible entity in this tenant — use list from rev_a.
    entities = graphs.list_snapshot_entities(
        rev_a.snapshot_id, tenant_id=ids.tenant_alpha
    )
    entity = entities[0]
    snap = RepositoryGraphSnapshot(
        snapshot_id=snap_id,
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_revision=REV_A,
        extraction_run_id=run_id,
        status=SnapshotStatus.BUILDING,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        coverage_status=CoverageStatus.COMPLETE,
        entity_count=1,
        relation_count=0,
        coverage_notes=("cas direct",),
    )
    graphs.save_building_snapshot(snap)
    graphs.save_extraction_run(
        RepositoryExtractionRun(
            extraction_run_id=run_id,
            snapshot_id=snap_id,
            provider_key="fake",
            provider_version="1",
            provider_schema_version="m2.fake.v1",
            configuration_hash="cfg",
            requested_revision=REV_A,
            actual_revision=REV_A,
            started_at=NOW,
            completed_at=NOW,
            status=ExtractionRunStatus.SUCCEEDED,
            created_by_actor_id=ids.human_owner,
            limits=ExtractionLimits(max_files=10),
        )
    )
    graphs.add_snapshot_entity_memberships(
        snapshot_id=snap_id,
        tenant_id=ids.tenant_alpha,
        entity_fact_ids=(entity.entity_fact_id,),
    )
    with pytest.raises(ContentionError, match="base_snapshot_not_current"):
        graphs.activate_snapshot(
            snap_id,
            tenant_id=ids.tenant_alpha,
            activated_at=NOW,
            expected_active_snapshot_id=generate_uuidv7(),
        )


# --- P1: Impact traversal cap ---


def test_impact_depth_11_hop_forces_fallback_full() -> None:
    entities = [
        _entity(path=f"hop_{i}.py", fact_id=generate_uuidv7()) for i in range(12)
    ]
    relations = tuple(
        _relation(
            kind=RelationKind.CALLS,
            source=entities[i],
            target=entities[i + 1],
        )
        for i in range(11)
    )
    plan = plan_incremental_refresh(
        changed_paths=("hop_0.py",),
        base_entities=tuple(entities),
        base_relations=relations,
    )
    assert plan.fallback_full is True
    assert plan.reextract_paths == frozenset()
    assert any("MAX_INCREMENTAL_IMPACT_DEPTH" in note for note in plan.notes)
    assert MAX_INCREMENTAL_IMPACT_DEPTH == 8


def test_impact_short_chain_stays_incremental() -> None:
    entities = [
        _entity(path=f"short_{i}.py", fact_id=generate_uuidv7()) for i in range(4)
    ]
    relations = tuple(
        _relation(
            kind=RelationKind.CALLS,
            source=entities[i],
            target=entities[i + 1],
        )
        for i in range(3)
    )
    plan = plan_incremental_refresh(
        changed_paths=("short_0.py",),
        base_entities=tuple(entities),
        base_relations=relations,
    )
    assert plan.fallback_full is False
    assert plan.reextract_paths == frozenset(
        {"short_0.py", "short_1.py", "short_2.py", "short_3.py"}
    )


# --- P1: Deleted source invalidation ---


def test_deleted_source_stales_dependent_module(tmp_path: Path) -> None:
    _conn, service, ids, binding_id, intel, graphs, _queries = _service()
    # Copy rev_a and build, then delete schema.py and rebuild incrementally.
    tree_a = tmp_path / "rev_a_copy"
    shutil.copytree(TREES_ROOT / "rev_a", tree_a)
    rev_hash_a = f"fixture:{tree_content_hash(tree_a)}"
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=rev_hash_a,
        tree=tree_a,
        idempotency_key="del-a",
    )
    assert rev_a.status is SnapshotStatus.ACTIVE

    schema_source_id = stable_source_id(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_relative_path="sample_app/schema.py",
    )
    service_source_id = stable_source_id(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_relative_path="sample_app/service.py",
    )
    schema_source = intel.get_source(schema_source_id)
    service_source = intel.get_source(service_source_id)
    assert schema_source is not None
    assert service_source is not None

    dependent = ContextModule(
        module_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        module_key="architecture",
        purpose_text="depends on schema.py",
        applicability_text="schema",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        revision=1,
        source_ids=(schema_source_id,),
        observation_ids=(schema_source.current_observation_id,),
    )
    unrelated = ContextModule(
        module_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        module_key="domain-language",
        purpose_text="depends on service.py",
        applicability_text="service",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        revision=1,
        source_ids=(service_source_id,),
        observation_ids=(service_source.current_observation_id,),
    )
    intel.save_context_module(dependent)
    intel.save_context_module(unrelated)

    tree_b = tmp_path / "rev_b_deleted"
    shutil.copytree(tree_a, tree_b)
    (tree_b / "sample_app" / "schema.py").unlink()
    rev_hash_b = f"fixture:{tree_content_hash(tree_b)}"
    inc = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=rev_hash_b,
        tree=tree_b,
        idempotency_key="del-b",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=("sample_app/schema.py",),
    )
    assert inc.status is SnapshotStatus.ACTIVE
    assert intel.get_context_module(dependent.module_id).freshness is StaleStatus.STALE
    assert intel.get_context_module(unrelated.module_id).freshness is StaleStatus.FRESH
    # Historical A intact.
    hist = graphs.list_snapshot_entities(rev_a.snapshot_id, tenant_id=ids.tenant_alpha)
    assert any(e.repository_relative_path == "sample_app/schema.py" for e in hist)


# --- P1: Graph readiness ---


def test_factual_graph_readiness_absent_partial_supported_stale() -> None:
    assert (
        evaluate_factual_graph_readiness(active_snapshot=None, active_run=None)
        is FactualGraphReadiness.ABSENT
    )

    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    status = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert status.factual_graph_readiness is FactualGraphReadiness.ABSENT
    view = queries.get_graph_readiness(
        GraphQueryScope(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
        )
    )
    assert view.readiness is FactualGraphReadiness.ABSENT

    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="ready-a",
    )
    assert rev_a.status is SnapshotStatus.ACTIVE
    status = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert status.factual_graph_readiness is FactualGraphReadiness.UNRESOLVED

    status_complete = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        observed_repository_revision=REV_A,
    )
    assert (
        status_complete.factual_graph_readiness
        is FactualGraphReadiness.COMPLETE_FOR_SUPPORTED_SCOPE
    )

    status_stale = service.get_status(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        observed_repository_revision=REV_B,
    )
    assert status_stale.factual_graph_readiness is FactualGraphReadiness.STALE

    snap = graphs.require_snapshot(rev_a.snapshot_id, tenant_id=ids.tenant_alpha)
    run = graphs.get_extraction_run(snap.extraction_run_id)
    assert (
        evaluate_factual_graph_readiness(
            active_snapshot=snap,
            active_run=run,
            binding_repository_revision=REV_B,
        )
        is FactualGraphReadiness.STALE
    )

    # Partial: synthesize a snapshot object with PARTIAL coverage.
    partial_snap = RepositoryGraphSnapshot(
        snapshot_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_revision=REV_A,
        extraction_run_id=snap.extraction_run_id,
        status=SnapshotStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        coverage_status=CoverageStatus.PARTIAL,
        entity_count=1,
        relation_count=0,
        coverage_notes=("partial fixture",),
        activated_at=NOW,
    )
    assert (
        evaluate_factual_graph_readiness(active_snapshot=partial_snap, active_run=run)
        is FactualGraphReadiness.PARTIAL
    )


# --- P2: Query budget omissions + sentinel related tests ---


def test_compare_snapshots_budget_omissions_fire() -> None:
    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="omit-a",
    )
    rev_b = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="omit-b",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    tiny = QueryBudget(max_depth=1, max_results=10, max_visited_nodes=1)
    result = queries.compare_snapshots(
        scope, rev_a.snapshot_id, rev_b.snapshot_id, budget=tiny
    )
    assert "max_visited_nodes" in result.omissions.reasons


def test_test_sentinel_preserves_related_unchanged_tests() -> None:
    prod = _entity(path="app.py", kind=EntityKind.MODULE, fact_id=generate_uuidv7())
    test = _entity(
        path="tests/test_app.py",
        kind=EntityKind.TEST,
        fact_id=generate_uuidv7(),
        qualified_name="tests.test_app",
    )
    rel = _relation(kind=RelationKind.TESTS, source=test, target=prod)
    findings = evaluate_sentinels(
        entities=(prod, test),
        relations=(rel,),
        coverage_status=CoverageStatus.COMPLETE,
        changed_paths=("app.py",),
    )
    assoc = next(f for f in findings if f.kind is SentinelKind.TEST_ASSOCIATION)
    assert test.entity_fact_id in assoc.entity_fact_ids
    assert "related_test" in assoc.evidence_notes


# --- Closeout re-review: activation CAS / atomicity / bounded queries ---


def test_full_rebuild_of_a_rejected_when_b_is_active() -> None:
    _conn, service, ids, binding_id, intel, graphs, _queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="full-a1",
    )
    rev_b = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="full-b1",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    assert rev_b.status is SnapshotStatus.ACTIVE

    # Stale expected active (A) while B is current — rejected.
    rejected = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="full-a-stale",
        expected_active_snapshot_id=rev_a.snapshot_id,
        expect_no_active_snapshot=False,
    )
    assert rejected.status is SnapshotStatus.FAILED
    assert "base_snapshot_not_current" in rejected.coverage_notes
    active = graphs.get_active_snapshot(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert active is not None
    assert active.snapshot_id == rev_b.snapshot_id

    # Sources must remain pointed at B's revision, not the failed rebuild of A.
    for row in _conn.execute(
        """
        SELECT observed_revision FROM gov_workspace_sources
        WHERE tenant_id = ? AND workspace_object_id = ?
          AND locator LIKE 'sample_app/%.py'
        """,
        (ids.tenant_alpha, ids.workspace_alpha_1),
    ):
        assert row["observed_revision"] == REV_B


def test_two_full_builds_same_expected_active_only_one_activates() -> None:
    _conn, service, ids, binding_id, _intel, graphs, _queries = _service()
    first = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="init-a",
    )
    assert first.status is SnapshotStatus.ACTIVE
    one = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="full-race-1",
        expected_active_snapshot_id=first.snapshot_id,
    )
    two = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="full-race-2",
        expected_active_snapshot_id=first.snapshot_id,
    )
    assert one.status is SnapshotStatus.ACTIVE
    assert two.status is SnapshotStatus.FAILED
    actives = _conn.execute(
        """
        SELECT COUNT(*) AS n FROM gov_code_graph_snapshots
        WHERE repository_binding_id = ? AND status = ?
        """,
        (binding_id, SnapshotStatus.ACTIVE.value),
    ).fetchone()["n"]
    assert actives == 1


def test_initial_build_requires_expect_no_active_snapshot() -> None:
    _conn, service, ids, binding_id, _intel, graphs, _queries = _service()
    ok = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="init-ok",
        expect_no_active_snapshot=True,
    )
    assert ok.status is SnapshotStatus.ACTIVE
    contested = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="init-contested",
        expect_no_active_snapshot=True,
    )
    assert contested.status is SnapshotStatus.FAILED
    assert "base_snapshot_not_current" in contested.coverage_notes


def test_failed_cas_leaves_source_observations_and_receipts_unchanged() -> None:
    conn, service, ids, binding_id, intel, graphs, _queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="atom-a",
    )
    rev_b = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="atom-b",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    before_sources = {
        str(row["locator"]): (
            str(row["observed_revision"]),
            str(row["current_observation_id"]),
            str(row["stale_status"]),
        )
        for row in conn.execute(
            """
            SELECT locator, observed_revision, current_observation_id, stale_status
            FROM gov_workspace_sources
            WHERE tenant_id = ? AND workspace_object_id = ?
            """,
            (ids.tenant_alpha, ids.workspace_alpha_1),
        )
    }
    before_events = conn.execute(
        "SELECT COUNT(*) AS n FROM gov_domain_events WHERE tenant_id = ?",
        (ids.tenant_alpha,),
    ).fetchone()["n"]
    before_receipts = conn.execute(
        "SELECT COUNT(*) AS n FROM gov_command_receipts WHERE tenant_id = ?",
        (ids.tenant_alpha,),
    ).fetchone()["n"]

    failed = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="atom-stale",
        expected_active_snapshot_id=rev_a.snapshot_id,
    )
    assert failed.status is SnapshotStatus.FAILED

    after_sources = {
        str(row["locator"]): (
            str(row["observed_revision"]),
            str(row["current_observation_id"]),
            str(row["stale_status"]),
        )
        for row in conn.execute(
            """
            SELECT locator, observed_revision, current_observation_id, stale_status
            FROM gov_workspace_sources
            WHERE tenant_id = ? AND workspace_object_id = ?
            """,
            (ids.tenant_alpha, ids.workspace_alpha_1),
        )
    }
    assert after_sources == before_sources
    active = graphs.get_active_snapshot(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert active is not None and active.snapshot_id == rev_b.snapshot_id
    # Failure records build-requested + build-failed events and a receipt, but
    # source pointers and the active graph must be unchanged.
    after_events = conn.execute(
        "SELECT COUNT(*) AS n FROM gov_domain_events WHERE tenant_id = ?",
        (ids.tenant_alpha,),
    ).fetchone()["n"]
    after_receipts = conn.execute(
        "SELECT COUNT(*) AS n FROM gov_command_receipts WHERE tenant_id = ?",
        (ids.tenant_alpha,),
    ).fetchone()["n"]
    assert after_events >= before_events + 1
    assert after_receipts == before_receipts + 1
    assert "workspace.code_graph.snapshot_activated" not in failed.event_types
    assert "workspace.code_graph.build_failed" in failed.event_types


def test_activation_fault_after_point_sources_rolls_back() -> None:
    _conn, service, ids, binding_id, intel, graphs, _queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="fault-a",
    )
    before = {
        source.locator: source.observed_revision
        for source in intel.list_sources(
            ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
        )
    }
    service._activation_fault_before = "after:point_sources"
    failed = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="fault-b",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    assert failed.status is SnapshotStatus.FAILED
    active = graphs.get_active_snapshot(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    assert active is not None and active.snapshot_id == rev_a.snapshot_id
    live_sources = intel.list_sources(ids.workspace_alpha_1, tenant_id=ids.tenant_alpha)
    live = {source.locator: source.observed_revision for source in live_sources}
    assert live == before
    assert all(revision == REV_A for revision in live.values())
    for source in live_sources:
        assert source.stale_status is not StaleStatus.STAGED
        assert source.current_observation_id is not None
        assert source.observed_revision != REV_B


def test_failed_initial_activation_excludes_staged_sources() -> None:
    conn, service, ids, binding_id, intel, graphs, _queries = _service()
    service._activation_fault_before = "point_sources"
    failed = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="fault-initial",
    )
    assert failed.status is SnapshotStatus.FAILED
    assert (
        graphs.get_active_snapshot(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
        )
        is None
    )
    assert intel.list_sources(ids.workspace_alpha_1, tenant_id=ids.tenant_alpha) == []
    staged_rows = conn.execute(
        """
        SELECT stale_status, current_observation_id, observed_revision
        FROM gov_workspace_sources
        WHERE tenant_id = ? AND workspace_object_id = ?
        """,
        (ids.tenant_alpha, ids.workspace_alpha_1),
    ).fetchall()
    assert staged_rows
    for row in staged_rows:
        assert str(row["stale_status"]) == StaleStatus.STAGED.value
        assert row["current_observation_id"] is None
        assert str(row["observed_revision"]) == REV_A


def test_entity_only_budget_excludes_contains_and_reads() -> None:
    from holodeck_governance.domain.workspace.intelligence.code_graph.queries import (
        TraversalDirection,
        neighbors_of,
    )

    file_ent = _entity(path="pkg/mod.py", kind=EntityKind.FILE)
    fn = _entity(path="pkg/mod.py", kind=EntityKind.FUNCTION, qualified_name="f")
    other = _entity(path="pkg/other.py", kind=EntityKind.FUNCTION, qualified_name="g")
    contains = _relation(kind=RelationKind.CONTAINS, source=file_ent, target=fn)
    reads = _relation(kind=RelationKind.READS, source=fn, target=other)
    calls = _relation(kind=RelationKind.CALLS, source=fn, target=other)
    budget = QueryBudget(
        max_depth=1,
        max_results=50,
        max_visited_nodes=50,
        entity_kinds=(EntityKind.FUNCTION,),
        relation_kinds=(),
    )
    hits, _omissions = neighbors_of(
        seed_entity_fact_id=fn.entity_fact_id,
        entities=(file_ent, fn, other),
        relations=(contains, reads, calls),
        direction=TraversalDirection.BOTH,
        budget=budget,
    )
    kinds = {hit.relation.relation_kind for hit in hits}
    assert RelationKind.CALLS in kinds
    assert RelationKind.CONTAINS not in kinds
    assert RelationKind.READS not in kinds


def test_bounded_find_entities_does_not_scan_entire_synthetic_graph() -> None:
    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="bound-base",
    )
    assert rev_a.entity_count > 20
    graphs.entities_rows_fetched = 0
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    budget = QueryBudget(max_depth=1, max_results=5, max_visited_nodes=50)
    result = queries.find_entities(scope, budget=budget)
    assert len(result.entities) == 5
    assert "max_results" in result.omissions.reasons
    # Storage fetches limit+1 rows — never the full snapshot entity set.
    assert graphs.entities_rows_fetched <= 6
    assert graphs.entities_rows_fetched < rev_a.entity_count


def test_change_neighborhood_marks_incomplete_when_visit_budget_truncates() -> None:
    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="nb-trunc-a",
    )
    assert rev_a.entity_count > 5
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    # Force the storage-bounded loader path with a tiny visit budget.
    tiny = QueryBudget(max_depth=2, max_results=50, max_visited_nodes=2)
    result = queries.get_change_neighborhood(
        scope,
        ("sample_app/service.py",),
        budget=tiny,
    )
    assert result.fallback_full is True
    assert "impact_neighborhood_incomplete" in result.omissions.reasons
    assert "impact_neighborhood_incomplete" in result.notes


def test_path_prefix_like_escapes_wildcards() -> None:
    _conn, service, ids, binding_id, _intel, graphs, _queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="like-a",
    )
    entities = graphs.list_snapshot_entities(
        rev_a.snapshot_id, tenant_id=ids.tenant_alpha
    )
    # Plant a sibling path that would match an unescaped underscore wildcard.
    donor = entities[0]
    wildcard_path = "pkgXa/two.py"
    literal_dir = "pkg_a"
    planted = CodeEntityFact(
        entity_fact_id=generate_uuidv7(),
        tenant_id=donor.tenant_id,
        workspace_object_id=donor.workspace_object_id,
        repository_binding_id=donor.repository_binding_id,
        entity_key=build_entity_key(
            entity_kind=EntityKind.FILE,
            repository_relative_path=wildcard_path,
            qualified_name=wildcard_path,
        ),
        entity_kind=EntityKind.FILE,
        repository_relative_path=wildcard_path,
        source_id=donor.source_id,
        source_observation_id=donor.source_observation_id,
        observation_method=ObservationMethod.DIRECT_PARSE,
        created_at=NOW,
        language="python",
        qualified_name=wildcard_path,
    )
    graphs.insert_entity_fact(planted)
    graphs.add_snapshot_entity_memberships(
        snapshot_id=rev_a.snapshot_id,
        tenant_id=ids.tenant_alpha,
        entity_fact_ids=(planted.entity_fact_id,),
    )
    literal = CodeEntityFact(
        entity_fact_id=generate_uuidv7(),
        tenant_id=donor.tenant_id,
        workspace_object_id=donor.workspace_object_id,
        repository_binding_id=donor.repository_binding_id,
        entity_key=build_entity_key(
            entity_kind=EntityKind.FILE,
            repository_relative_path=f"{literal_dir}/one.py",
            qualified_name=f"{literal_dir}/one.py",
        ),
        entity_kind=EntityKind.FILE,
        repository_relative_path=f"{literal_dir}/one.py",
        source_id=donor.source_id,
        source_observation_id=donor.source_observation_id,
        observation_method=ObservationMethod.DIRECT_PARSE,
        created_at=NOW,
        language="python",
        qualified_name=f"{literal_dir}/one.py",
    )
    graphs.insert_entity_fact(literal)
    graphs.add_snapshot_entity_memberships(
        snapshot_id=rev_a.snapshot_id,
        tenant_id=ids.tenant_alpha,
        entity_fact_ids=(literal.entity_fact_id,),
    )
    hits = graphs.find_snapshot_entities(
        rev_a.snapshot_id,
        tenant_id=ids.tenant_alpha,
        path_prefix=literal_dir,
        limit=50,
    )
    paths = {entity.repository_relative_path for entity in hits}
    assert f"{literal_dir}/one.py" in paths
    assert wildcard_path not in paths


def test_get_sources_for_facts_bounds_ids_before_sql() -> None:
    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="prov-bound-a",
    )
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    # Far beyond typical SQLITE_MAX_VARIABLE_NUMBER; must not raise.
    huge_ids = tuple(generate_uuidv7() for _ in range(40_000))
    tiny = QueryBudget(max_depth=1, max_results=3, max_visited_nodes=5)
    result = queries.get_sources_for_facts(
        scope,
        entity_fact_ids=huge_ids,
        relation_fact_ids=huge_ids,
        budget=tiny,
    )
    assert "max_visited_nodes" in result.omissions.reasons
    assert len(result.provenance) <= tiny.max_results


def test_changed_paths_budget_forces_full_fallback() -> None:
    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="paths-budget-a",
    )
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    # Unmatched paths: no loader overflow can hide the path-budget omission.
    changed = ("unknown-a.py", "unknown-b.py")
    tiny = QueryBudget(max_depth=1, max_results=50, max_visited_nodes=1)
    result = queries.get_change_neighborhood(scope, changed, budget=tiny)
    assert result.changed_paths == changed
    assert result.fallback_full is True
    assert "changed_paths_budget" in result.omissions.reasons
    assert "impact_neighborhood_incomplete" in result.omissions.reasons
    assert result.reextract_paths == ()
    assert "incremental_plan_unusable" in result.notes


def test_change_neighborhood_aggregate_entity_budget_bounds_storage() -> None:
    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="agg-budget-a",
    )
    assert rev_a.entity_count > 20
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    seed_paths = (
        "sample_app/api.py",
        "sample_app/base.py",
        "sample_app/service.py",
        "sample_app/store.py",
        "sample_app/schema.py",
    )
    budget = QueryBudget(max_depth=2, max_results=50, max_visited_nodes=5)
    graphs.entities_rows_fetched = 0
    result = queries.get_change_neighborhood(scope, seed_paths, budget=budget)
    # Aggregate remaining+1 probes: at most one overflow row beyond the budget.
    assert graphs.entities_rows_fetched <= budget.max_visited_nodes + 1
    assert result.fallback_full is True
    assert "impact_neighborhood_incomplete" in result.omissions.reasons


def test_change_neighborhood_counts_repeated_expansion_rows() -> None:
    """Raw storage rows from endpoint + path expansion share one visit budget."""

    conn, service, ids, binding_id, intel, graphs, queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="raw-rows-a",
    )
    donor = graphs.list_snapshot_entities(
        rev_a.snapshot_id, tenant_id=ids.tenant_alpha
    )[0]

    def _synth(path: str, *, kind: EntityKind = EntityKind.FUNCTION) -> CodeEntityFact:
        return CodeEntityFact(
            entity_fact_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            entity_key=build_entity_key(
                entity_kind=kind,
                repository_relative_path=path,
                qualified_name=path,
            ),
            entity_kind=kind,
            repository_relative_path=path,
            source_id=donor.source_id,
            source_observation_id=donor.source_observation_id,
            observation_method=ObservationMethod.DIRECT_PARSE,
            created_at=NOW,
            language="python",
            qualified_name=path,
        )

    seed = _synth("seed/caller.py")
    targets = tuple(_synth(f"targets/t{i}.py") for i in range(6))
    entities = (seed, *targets)
    relations = tuple(
        _relation(kind=RelationKind.CALLS, source=seed, target=target)
        for target in targets
    )
    # Pad with extra unused entities so snapshot exceeds the visit budget and
    # forces the storage-bounded loader path.
    padding = tuple(_synth(f"pad/p{i}.py") for i in range(20))
    all_entities = (*entities, *padding)
    run_id = generate_uuidv7()
    snap_id = generate_uuidv7()
    snapshot = RepositoryGraphSnapshot(
        snapshot_id=snap_id,
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_revision=REV_A,
        extraction_run_id=run_id,
        status=SnapshotStatus.BUILDING,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        coverage_status=CoverageStatus.COMPLETE,
        entity_count=len(all_entities),
        relation_count=len(relations),
        coverage_notes=("raw-row budget fixture",),
    )
    run = RepositoryExtractionRun(
        extraction_run_id=run_id,
        snapshot_id=snap_id,
        provider_key="fake",
        provider_version="1",
        provider_schema_version="m2.fake.v1",
        configuration_hash="cfg",
        requested_revision=REV_A,
        actual_revision=REV_A,
        started_at=NOW,
        completed_at=NOW,
        status=ExtractionRunStatus.SUCCEEDED,
        created_by_actor_id=ids.human_owner,
        limits=ExtractionLimits(max_files=100),
    )
    graphs.persist_building_graph(
        snapshot=snapshot,
        run=run,
        entities=all_entities,
        relations=relations,
    )
    graphs.activate_snapshot(
        snap_id,
        tenant_id=ids.tenant_alpha,
        activated_at=NOW,
        expected_active_snapshot_id=rev_a.snapshot_id,
    )
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    budget = QueryBudget(max_depth=2, max_results=50, max_visited_nodes=10)
    graphs.entities_rows_fetched = 0
    graphs.relations_rows_fetched = 0
    result = queries.get_change_neighborhood(scope, ("seed/caller.py",), budget=budget)
    assert len(result.entities) <= budget.max_visited_nodes
    assert graphs.entities_rows_fetched <= budget.max_visited_nodes + 1
    assert graphs.relations_rows_fetched <= budget.max_visited_nodes + 1
    assert result.fallback_full is True
    assert "impact_neighborhood_incomplete" in result.omissions.reasons


def _activate_synthetic_snapshot(
    *,
    graphs: SqliteCodeGraphRepository,
    ids: FixtureIds,
    binding_id: str,
    expected_active_snapshot_id: str,
    entities: tuple[CodeEntityFact, ...],
    relations: tuple[CodeRelationFact, ...],
    note: str,
) -> str:
    run_id = generate_uuidv7()
    snap_id = generate_uuidv7()
    snapshot = RepositoryGraphSnapshot(
        snapshot_id=snap_id,
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_revision=REV_A,
        extraction_run_id=run_id,
        status=SnapshotStatus.BUILDING,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        coverage_status=CoverageStatus.COMPLETE,
        entity_count=len(entities),
        relation_count=len(relations),
        coverage_notes=(note,),
    )
    run = RepositoryExtractionRun(
        extraction_run_id=run_id,
        snapshot_id=snap_id,
        provider_key="fake",
        provider_version="1",
        provider_schema_version="m2.fake.v1",
        configuration_hash="cfg",
        requested_revision=REV_A,
        actual_revision=REV_A,
        started_at=NOW,
        completed_at=NOW,
        status=ExtractionRunStatus.SUCCEEDED,
        created_by_actor_id=ids.human_owner,
        limits=ExtractionLimits(max_files=100),
    )
    graphs.persist_building_graph(
        snapshot=snapshot,
        run=run,
        entities=entities,
        relations=relations,
    )
    graphs.activate_snapshot(
        snap_id,
        tenant_id=ids.tenant_alpha,
        activated_at=NOW,
        expected_active_snapshot_id=expected_active_snapshot_id,
    )
    return snap_id


def test_change_neighborhood_multihop_includes_downstream() -> None:
    """A→B→C must expand B so C is discovered under the bounded loader."""

    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="multihop-a",
    )
    donor = graphs.list_snapshot_entities(
        rev_a.snapshot_id, tenant_id=ids.tenant_alpha
    )[0]

    def _synth(path: str) -> CodeEntityFact:
        return CodeEntityFact(
            entity_fact_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            entity_key=build_entity_key(
                entity_kind=EntityKind.FUNCTION,
                repository_relative_path=path,
                qualified_name=path,
            ),
            entity_kind=EntityKind.FUNCTION,
            repository_relative_path=path,
            source_id=donor.source_id,
            source_observation_id=donor.source_observation_id,
            observation_method=ObservationMethod.DIRECT_PARSE,
            created_at=NOW,
            language="python",
            qualified_name=path,
        )

    node_a = _synth("chain/a.py")
    node_b = _synth("chain/b.py")
    node_c = _synth("chain/c.py")
    chain_entities = (node_a, node_b, node_c)
    chain_relations = (
        _relation(kind=RelationKind.CALLS, source=node_a, target=node_b),
        _relation(kind=RelationKind.CALLS, source=node_b, target=node_c),
    )
    padding = tuple(_synth(f"pad/m{i}.py") for i in range(20))
    _activate_synthetic_snapshot(
        graphs=graphs,
        ids=ids,
        binding_id=binding_id,
        expected_active_snapshot_id=rev_a.snapshot_id,
        entities=(*chain_entities, *padding),
        relations=chain_relations,
        note="multihop A→B→C",
    )
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    # Generous budget so incompleteness cannot hide a frontier bug.
    budget = QueryBudget(max_depth=4, max_results=50, max_visited_nodes=30)
    result = queries.get_change_neighborhood(scope, ("chain/a.py",), budget=budget)
    paths = {entity.repository_relative_path for entity in result.entities}
    assert "chain/a.py" in paths
    assert "chain/b.py" in paths
    assert "chain/c.py" in paths
    assert {rel.relation_fact_id for rel in result.relations} >= {
        chain_relations[0].relation_fact_id,
        chain_relations[1].relation_fact_id,
    } or len(result.relations) >= 2
    assert result.fallback_full is False
    assert "impact_neighborhood_incomplete" not in result.omissions.reasons


def test_change_neighborhood_cycle_terminates() -> None:
    """A→B→A must terminate without looping forever under the bounded loader."""

    _conn, service, ids, binding_id, _intel, graphs, queries = _service()
    rev_a = _build(
        service,
        ids,
        binding_id,
        graphs=graphs,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="cycle-a",
    )
    donor = graphs.list_snapshot_entities(
        rev_a.snapshot_id, tenant_id=ids.tenant_alpha
    )[0]

    def _synth(path: str) -> CodeEntityFact:
        return CodeEntityFact(
            entity_fact_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            entity_key=build_entity_key(
                entity_kind=EntityKind.FUNCTION,
                repository_relative_path=path,
                qualified_name=path,
            ),
            entity_kind=EntityKind.FUNCTION,
            repository_relative_path=path,
            source_id=donor.source_id,
            source_observation_id=donor.source_observation_id,
            observation_method=ObservationMethod.DIRECT_PARSE,
            created_at=NOW,
            language="python",
            qualified_name=path,
        )

    node_a = _synth("cycle/a.py")
    node_b = _synth("cycle/b.py")
    cycle_entities = (node_a, node_b)
    cycle_relations = (
        _relation(kind=RelationKind.CALLS, source=node_a, target=node_b),
        _relation(kind=RelationKind.CALLS, source=node_b, target=node_a),
    )
    padding = tuple(_synth(f"pad/c{i}.py") for i in range(20))
    _activate_synthetic_snapshot(
        graphs=graphs,
        ids=ids,
        binding_id=binding_id,
        expected_active_snapshot_id=rev_a.snapshot_id,
        entities=(*cycle_entities, *padding),
        relations=cycle_relations,
        note="cycle A→B→A",
    )
    scope = GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
    )
    budget = QueryBudget(max_depth=4, max_results=50, max_visited_nodes=30)
    graphs.entities_rows_fetched = 0
    graphs.relations_rows_fetched = 0
    result = queries.get_change_neighborhood(scope, ("cycle/a.py",), budget=budget)
    paths = {entity.repository_relative_path for entity in result.entities}
    assert paths >= {"cycle/a.py", "cycle/b.py"}
    assert len(result.relations) >= 1
    # Expanded frontier IDs prevent re-querying A forever; counters stay bounded.
    assert graphs.entities_rows_fetched <= budget.max_visited_nodes + 1
    assert graphs.relations_rows_fetched <= budget.max_visited_nodes + 1
    assert result.fallback_full is False
