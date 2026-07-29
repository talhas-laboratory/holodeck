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

from python_reference import (
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
    base_snapshot_id: str | None = None,
    changed_paths: tuple[str, ...] = (),
    path_includes: tuple[str, ...] = (),
) -> object:
    path = Path(tree) if isinstance(tree, Path) else TREES_ROOT / tree
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
            changed_paths=("sample_app/service.py",),
        )


def test_fallback_full_extract_equals_standalone_full_on_golden() -> None:
    _conn, service, ids, binding_id, _intel, graphs, _queries = _service()
    rev_a = _build(
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="p0-a"
    )
    # Force fallback by empty changed_paths with base (still allowed).
    fallback = _build(
        service,
        ids,
        binding_id,
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
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="cas-a"
    )
    assert rev_a.status is SnapshotStatus.ACTIVE
    rev_b = _build(
        service,
        ids,
        binding_id,
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
    _conn, service, ids, binding_id, _intel, _graphs, _queries = _service()
    rev_a = _build(
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="race-a"
    )
    first = _build(
        service,
        ids,
        binding_id,
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
    assert (
        status.factual_graph_readiness
        is FactualGraphReadiness.COMPLETE_FOR_SUPPORTED_SCOPE
    )

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
    _conn, service, ids, binding_id, _intel, _graphs, queries = _service()
    rev_a = _build(
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="omit-a"
    )
    rev_b = _build(
        service,
        ids,
        binding_id,
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
