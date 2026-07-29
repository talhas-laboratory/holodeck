"""M2-024 safe incremental code-graph refresh and invalidation."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from holodeck_governance.adapters.code_graph.python_ast import (
    PythonStdlibAstExtractor,
    stable_source_id,
)
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
    ContextModule,
    ModuleApprovalStatus,
    StaleStatus,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeEntityFact,
    CodeRelationFact,
    EntityKind,
    ExtractionLimits,
    ObservationMethod,
    RelationKind,
    SnapshotStatus,
    SourceSpan,
    build_entity_key,
    compare_normalized_snapshots,
    merge_incremental_facts,
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

NOW = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)
REV_A = fixture_revision_id("rev_a")
REV_B = fixture_revision_id("rev_b")
LIMITS = ExtractionLimits(max_files=200, max_entities=5000, max_relations=20000)


def _changed_paths_rev_b() -> tuple[str, ...]:
    payload = json.loads(REVISIONS_PATH.read_text(encoding="utf-8"))
    return tuple(payload["revisions"]["rev_b"]["changed_paths_from_rev_a"])


def _service() -> (
    tuple[
        sqlite3.Connection,
        CodeGraphIngestionService,
        FixtureIds,
        str,
        SqliteWorkspaceIntelligenceRepository,
        SqliteCodeGraphRepository,
    ]
):
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
    service = CodeGraphIngestionService(
        collaboration=collab,
        intelligence=intelligence,
        graphs=graphs,
        extractor=PythonStdlibAstExtractor(),
        events=SqliteDomainEventRepository(conn),
        receipts=SqliteCommandReceiptRepository(conn),
        commit=conn.commit,
    )
    return conn, service, ids, binding.binding_id, intelligence, graphs


def _build(
    service: CodeGraphIngestionService,
    ids: FixtureIds,
    binding_id: str,
    *,
    revision: str,
    tree: str,
    idempotency_key: str,
    base_snapshot_id: str | None = None,
    changed_paths: tuple[str, ...] = (),
) -> object:
    return service.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / tree,
            requested_revision=revision,
            actor_id=ids.human_owner,
            idempotency_key=idempotency_key,
            limits=LIMITS,
            at=NOW,
            base_snapshot_id=base_snapshot_id,
            changed_paths=changed_paths,
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


def test_plan_expands_impact_neighborhood_without_contains() -> None:
    a = _entity(path="a.py", fact_id=generate_uuidv7())
    b = _entity(path="b.py", fact_id=generate_uuidv7())
    c = _entity(path="c.py", fact_id=generate_uuidv7())
    d = _entity(path="d.py", fact_id=generate_uuidv7())
    entities = (a, b, c, d)
    relations = (
        _relation(kind=RelationKind.IMPORTS, source=a, target=b),
        _relation(kind=RelationKind.CALLS, source=b, target=c),
        _relation(kind=RelationKind.CONTAINS, source=d, target=a),
    )
    plan = plan_incremental_refresh(
        changed_paths=("a.py",),
        base_entities=entities,
        base_relations=relations,
    )
    assert plan.fallback_full is False
    assert plan.reextract_paths == frozenset({"a.py", "b.py", "c.py"})
    assert "d.py" not in plan.reextract_paths


def test_plan_empty_changed_paths_falls_back() -> None:
    plan = plan_incremental_refresh(
        changed_paths=(),
        base_entities=(),
        base_relations=(),
    )
    assert plan.fallback_full is True
    assert plan.reextract_paths == frozenset()


def test_merge_reuses_unchanged_and_rebuilds_changed() -> None:
    stable = _entity(path="stable.py", fact_id=generate_uuidv7())
    stable_fn = _entity(
        path="stable.py",
        kind=EntityKind.FUNCTION,
        fact_id=generate_uuidv7(),
        qualified_name="stable.fn",
    )
    old_changed = _entity(path="changed.py", fact_id=generate_uuidv7())
    new_changed = _entity(path="changed.py", fact_id=generate_uuidv7())
    new_fn = _entity(
        path="changed.py",
        kind=EntityKind.FUNCTION,
        fact_id=generate_uuidv7(),
        qualified_name="changed.fn",
    )
    base_rel = _relation(kind=RelationKind.DEFINES, source=stable, target=stable_fn)
    extract_rel = _relation(
        kind=RelationKind.DEFINES, source=new_changed, target=new_fn
    )
    entities, relations, stats = merge_incremental_facts(
        base_entities=(stable, stable_fn, old_changed),
        base_relations=(base_rel,),
        extracted_entities=(new_changed, new_fn),
        extracted_relations=(extract_rel,),
        reextract_paths=frozenset({"changed.py"}),
    )
    ids = {entity.entity_fact_id for entity in entities}
    assert stable.entity_fact_id in ids
    assert old_changed.entity_fact_id not in ids
    assert new_changed.entity_fact_id in ids
    assert stats.reused_entities == 2
    assert stats.rebuilt_entities == 2
    assert stats.reused_relations == 1
    assert stats.rebuilt_relations == 1
    assert len(relations) == 2


def test_incremental_matches_full_normalized_facts_on_golden() -> None:
    conn, service, ids, binding_id, _intel, graphs = _service()
    changed = _changed_paths_rev_b()

    rev_a = _build(
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="rev-a"
    )
    assert rev_a.status is SnapshotStatus.ACTIVE

    started_full = time.perf_counter()
    full_b = _build(
        service,
        ids,
        binding_id,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="rev-b-full",
    )
    full_elapsed = time.perf_counter() - started_full
    assert full_b.status is SnapshotStatus.ACTIVE

    # Rebuild a fresh world so incremental starts from an active rev_a base.
    conn2, service2, ids2, binding_id2, _intel2, graphs2 = _service()
    rev_a2 = _build(
        service2,
        ids2,
        binding_id2,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="rev-a",
    )
    started_inc = time.perf_counter()
    inc_b = _build(
        service2,
        ids2,
        binding_id2,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="rev-b-inc",
        base_snapshot_id=rev_a2.snapshot_id,
        changed_paths=changed,
    )
    inc_elapsed = time.perf_counter() - started_inc
    assert inc_b.status is SnapshotStatus.ACTIVE
    assert inc_b.incremental is True
    assert inc_b.fallback_full is False
    assert inc_b.reused_entity_count > 0
    assert inc_b.rebuilt_entity_count > 0

    full_entities = graphs.list_snapshot_entities(
        full_b.snapshot_id, tenant_id=ids.tenant_alpha
    )
    full_relations = graphs.list_snapshot_relations(
        full_b.snapshot_id, tenant_id=ids.tenant_alpha
    )
    inc_entities = graphs2.list_snapshot_entities(
        inc_b.snapshot_id, tenant_id=ids2.tenant_alpha
    )
    inc_relations = graphs2.list_snapshot_relations(
        inc_b.snapshot_id, tenant_id=ids2.tenant_alpha
    )
    comparison = compare_normalized_snapshots(
        full_entities, full_relations, inc_entities, inc_relations
    )
    assert comparison.only_left_entities == 0
    assert comparison.only_right_entities == 0
    assert comparison.only_left_relations == 0
    assert comparison.only_right_relations == 0

    prior = graphs2.get_snapshot(rev_a2.snapshot_id)
    assert prior is not None
    assert prior.status is SnapshotStatus.SUPERSEDED
    prior_entities = graphs2.list_snapshot_entities(
        rev_a2.snapshot_id, tenant_id=ids2.tenant_alpha
    )
    assert prior_entities

    metrics = {
        "changed_paths": list(changed),
        "full": {
            "entity_count": full_b.entity_count,
            "relation_count": full_b.relation_count,
            "seconds": round(full_elapsed, 4),
            "entity_fingerprint_count": len(
                {entity.entity_key for entity in full_entities}
            ),
            "relation_fingerprint_count": comparison.matching_relations,
        },
        "incremental": {
            "entity_count": inc_b.entity_count,
            "relation_count": inc_b.relation_count,
            "seconds": round(inc_elapsed, 4),
            "reused_entity_count": inc_b.reused_entity_count,
            "rebuilt_entity_count": inc_b.rebuilt_entity_count,
            "reused_relation_count": inc_b.reused_relation_count,
            "rebuilt_relation_count": inc_b.rebuilt_relation_count,
            "fallback_full": inc_b.fallback_full,
        },
        "equivalence": {
            "matching_entities": comparison.matching_entities,
            "matching_relations": comparison.matching_relations,
            "only_left_entities": comparison.only_left_entities,
            "only_right_entities": comparison.only_right_entities,
            "only_left_relations": comparison.only_left_relations,
            "only_right_relations": comparison.only_right_relations,
        },
        "residual_risks": [
            "Neighborhood re-extraction stamps new observations on impact "
            "neighbors even when file bytes are unchanged.",
            "Rename/delete without an explicit changed-path entry still requires "
            "full fallback or an adapter-provided path set.",
        ],
    }
    artifact = ROOT / "artifacts" / "m2-024-incremental-refresh-metrics.json"
    artifact.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")


def test_incremental_reuses_unchanged_fact_ids() -> None:
    _conn, service, ids, binding_id, _intel, graphs = _service()
    rev_a = _build(
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="rev-a"
    )
    base_entities = graphs.list_snapshot_entities(
        rev_a.snapshot_id, tenant_id=ids.tenant_alpha
    )
    unchanged = next(
        entity
        for entity in base_entities
        if entity.repository_relative_path == "sample_app/schema.py"
    )
    inc = _build(
        service,
        ids,
        binding_id,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="rev-b-inc",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    assert inc.status is SnapshotStatus.ACTIVE
    membership = {
        entity.entity_fact_id
        for entity in graphs.list_snapshot_entities(
            inc.snapshot_id, tenant_id=ids.tenant_alpha
        )
    }
    assert unchanged.entity_fact_id in membership


def test_missing_changed_paths_with_base_falls_back_or_full() -> None:
    _conn, service, ids, binding_id, _intel, _graphs = _service()
    rev_a = _build(
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="rev-a"
    )
    result = _build(
        service,
        ids,
        binding_id,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="rev-b-no-paths",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=(),
    )
    assert result.status is SnapshotStatus.ACTIVE
    assert result.fallback_full is True
    assert result.incremental is True
    assert result.reused_entity_count == 0


def test_fallback_when_neighborhood_unsafe() -> None:
    _conn, service, ids, binding_id, _intel, _graphs = _service()
    rev_a = _build(
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="rev-a"
    )
    result = _build(
        service,
        ids,
        binding_id,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="rev-b-empty-paths",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=(),
    )
    assert result.fallback_full is True
    assert result.status is SnapshotStatus.ACTIVE


def test_changed_source_stales_dependent_module() -> None:
    _conn, service, ids, binding_id, intel, graphs = _service()
    rev_a = _build(
        service, ids, binding_id, revision=REV_A, tree="rev_a", idempotency_key="rev-a"
    )
    service_source_id = stable_source_id(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_relative_path="sample_app/service.py",
    )
    schema_source_id = stable_source_id(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        repository_relative_path="sample_app/schema.py",
    )
    service_source = intel.get_source(service_source_id)
    schema_source = intel.get_source(schema_source_id)
    assert service_source is not None
    assert schema_source is not None

    dependent = ContextModule(
        module_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        module_key="architecture",
        purpose_text="depends on service.py",
        applicability_text="service changes",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        revision=1,
        source_ids=(service_source_id,),
        observation_ids=(service_source.current_observation_id,),
    )
    unrelated = ContextModule(
        module_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        module_key="domain-language",
        purpose_text="depends on schema.py",
        applicability_text="schema changes",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        revision=1,
        source_ids=(schema_source_id,),
        observation_ids=(schema_source.current_observation_id,),
    )
    intel.save_context_module(dependent)
    intel.save_context_module(unrelated)

    inc = _build(
        service,
        ids,
        binding_id,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="rev-b-stale",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=_changed_paths_rev_b(),
    )
    assert inc.status is SnapshotStatus.ACTIVE
    assert (
        intel.get_context_module(dependent.module_id).freshness is StaleStatus.STALE
    )
    assert (
        intel.get_context_module(unrelated.module_id).freshness is StaleStatus.FRESH
    )
    # Prior snapshot membership remains queryable after supersession.
    assert graphs.list_snapshot_entities(
        rev_a.snapshot_id, tenant_id=ids.tenant_alpha
    )
