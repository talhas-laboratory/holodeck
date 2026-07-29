"""M2-026 end-to-end factual code-graph lifecycle acceptance.

Proves onboard → build rev_a → query → incremental/full rev_b → history →
stale propagation → failure modes, and writes acceptance metrics for the M3
handoff. Does not complete M2-011 consolidation.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread

import pytest

from holodeck_governance.adapters.code_graph.python_ast import (
    PythonStdlibAstExtractor,
    stable_source_id,
)
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
    M2_EVENT_CODE_GRAPH_BUILD_COMPLETED,
    M2_EVENT_CODE_GRAPH_BUILD_FAILED,
    M2_EVENT_CODE_GRAPH_BUILD_PARTIAL,
    M2_EVENT_CODE_GRAPH_BUILD_REQUESTED,
    M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED,
    ContextModule,
    ModuleApprovalStatus,
    StaleStatus,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeEntityFact,
    CoverageStatus,
    EntityKind,
    ExtractionLimits,
    ExtractionRunStatus,
    ObservationMethod,
    QueryBudget,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    SentinelStatus,
    SnapshotStatus,
    TraversalDirection,
    build_entity_key,
    compare_normalized_snapshots,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.code_graph import SqliteCodeGraphRepository
from holodeck_governance.storage.sqlite.collaboration import (
    SqliteCollaborationRepository,
)
from holodeck_governance.storage.sqlite.intelligence import (
    SqliteWorkspaceIntelligenceRepository,
)
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
)
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

NOW = datetime(2026, 7, 29, 19, 0, tzinfo=UTC)
REV_A = fixture_revision_id("rev_a")
REV_B = fixture_revision_id("rev_b")
LIMITS = ExtractionLimits(max_files=200, max_entities=5000, max_relations=20000)
BUDGET = QueryBudget(max_depth=4, max_results=200, max_visited_nodes=500)

_FORBIDDEN_EVENT_FRAGMENTS = (
    "system prompt",
    "you are an ai",
    "ignore previous instructions",
    "interpret this as",
    "instruction authority",
    "provider prompt",
)


def _changed_paths_rev_b() -> tuple[str, ...]:
    payload = json.loads(REVISIONS_PATH.read_text(encoding="utf-8"))
    return tuple(payload["revisions"]["rev_b"]["changed_paths_from_rev_a"])


def _world() -> tuple[
    sqlite3.Connection,
    CodeGraphIngestionService,
    CodeGraphQueryService,
    FixtureIds,
    str,
    SqliteWorkspaceIntelligenceRepository,
    SqliteCodeGraphRepository,
]:
    """Fresh migrate_governance DB with curate grant + active repo binding."""

    ids = FixtureIds()
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    migrate_governance(conn)
    assert governance_schema_version(conn) >= 24
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
        external_object_id="repo-acceptance",
        locator="git://example/acceptance",
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
        external_repository_id="repo-acceptance",
        canonical_locator="git://example/acceptance",
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
    return conn, ingestion, queries, ids, binding.binding_id, intelligence, graphs


def _scope(
    ids: FixtureIds, binding_id: str, *, snapshot_id: str | None = None
) -> GraphQueryScope:
    return GraphQueryScope(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        repository_binding_id=binding_id,
        snapshot_id=snapshot_id,
    )


def _build(
    ingestion: CodeGraphIngestionService,
    ids: FixtureIds,
    binding_id: str,
    *,
    revision: str,
    tree: str,
    idempotency_key: str,
    base_snapshot_id: str | None = None,
    changed_paths: tuple[str, ...] = (),
    limits: ExtractionLimits = LIMITS,
) -> object:
    return ingestion.build_graph(
        GraphBuildRequest(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding_id,
            repository_path=TREES_ROOT / tree,
            requested_revision=revision,
            actor_id=ids.human_owner,
            idempotency_key=idempotency_key,
            limits=limits,
            at=NOW,
            base_snapshot_id=base_snapshot_id,
            changed_paths=changed_paths,
        )
    )


def _event_payloads(conn: sqlite3.Connection, tenant_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT event_type, payload_json FROM gov_domain_events
        WHERE tenant_id = ?
        ORDER BY ledger_sequence
        """,
        (tenant_id,),
    ).fetchall()
    return [
        {
            "event_type": str(row["event_type"]),
            "payload": json.loads(row["payload_json"]),
        }
        for row in rows
    ]


def test_m2_026_factual_graph_lifecycle_acceptance() -> None:
    conn, ingestion, queries, ids, binding_id, intel, graphs = _world()
    changed = _changed_paths_rev_b()
    metrics: dict[str, object] = {
        "task": "M2-026",
        "schema_version": governance_schema_version(conn),
        "fixture": {
            "rev_a": REV_A,
            "rev_b": REV_B,
            "changed_paths": list(changed),
        },
        "steps": {},
        "pass": True,
    }

    # --- 1–2. Build rev_a ---
    started_a = time.perf_counter()
    rev_a = _build(
        ingestion,
        ids,
        binding_id,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="m2-026-rev-a",
    )
    rev_a_seconds = time.perf_counter() - started_a
    assert rev_a.status is SnapshotStatus.ACTIVE
    assert rev_a.actual_revision == REV_A
    assert rev_a.entity_count > 0
    assert rev_a.relation_count > 0
    assert M2_EVENT_CODE_GRAPH_BUILD_REQUESTED in rev_a.event_types
    assert (
        M2_EVENT_CODE_GRAPH_BUILD_COMPLETED in rev_a.event_types
        or M2_EVENT_CODE_GRAPH_BUILD_PARTIAL in rev_a.event_types
    )
    assert M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED in rev_a.event_types
    metrics["steps"]["build_rev_a"] = {
        "status": "pass",
        "snapshot_id": rev_a.snapshot_id,
        "entity_count": rev_a.entity_count,
        "relation_count": rev_a.relation_count,
        "seconds": round(rev_a_seconds, 4),
    }

    scope = _scope(ids, binding_id)

    # --- 3. Query entities, neighbors, traverse, provenance, sentinels ---
    kind_seeds = {
        EntityKind.MODULE: "sample_app/service.py",
        EntityKind.CLASS: "sample_app/service.py",
        EntityKind.API_ENTRY_POINT: None,
        EntityKind.TEST: None,
        EntityKind.SCHEMA_OBJECT: "sample_app/schema.py",
        EntityKind.MIGRATION: None,
        EntityKind.MANIFEST: None,
        EntityKind.CONFIGURATION: None,
    }
    found_kinds: dict[str, int] = {}
    for kind, path in kind_seeds.items():
        result = queries.find_entities(
            scope,
            path=path,
            entity_kinds=(kind,),
            budget=BUDGET,
        )
        assert result.entities, f"expected entities for {kind.value}"
        found_kinds[kind.value] = len(result.entities)

    greeter = queries.find_entities(
        scope,
        path="sample_app/service.py",
        entity_kinds=(EntityKind.CLASS,),
        qualified_name="Greeter",
        budget=BUDGET,
    ).entities[0]
    assert greeter.qualified_name == "sample_app.service.Greeter"

    neighbors = queries.get_neighbors(
        scope,
        greeter.entity_fact_id,
        direction=TraversalDirection.BOTH,
        budget=BUDGET,
    )
    assert neighbors.neighbors

    traversed = queries.traverse_paths(
        scope,
        greeter.entity_fact_id,
        direction=TraversalDirection.OUTGOING,
        budget=QueryBudget(max_depth=2, max_results=50, max_visited_nodes=100),
    )
    assert traversed.paths or "max_depth" in traversed.omissions.reasons

    sources = queries.get_sources_for_facts(
        scope, entity_fact_ids=(greeter.entity_fact_id,)
    )
    assert sources.provenance
    assert sources.provenance[0].observation_id
    assert sources.provenance[0].source_id

    sentinels = queries.evaluate_sentinels(scope)
    assert sentinels.findings
    assert all(
        finding.status in (SentinelStatus.ACTIVATED, SentinelStatus.UNRESOLVED)
        for finding in sentinels.findings
    )
    assert all(finding.status.value != "cleared" for finding in sentinels.findings)
    metrics["steps"]["queries"] = {
        "status": "pass",
        "kinds_found": found_kinds,
        "neighbor_count": len(neighbors.neighbors),
        "sentinel_count": len(sentinels.findings),
        "sentinel_statuses": sorted(
            {finding.status.value for finding in sentinels.findings}
        ),
    }

    # --- 4–5. Incremental rev_b + full rebuild equivalence ---
    started_inc = time.perf_counter()
    inc_b = _build(
        ingestion,
        ids,
        binding_id,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="m2-026-rev-b-inc",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=changed,
    )
    inc_seconds = time.perf_counter() - started_inc
    assert inc_b.status is SnapshotStatus.ACTIVE
    assert inc_b.incremental is True
    assert inc_b.fallback_full is False
    assert inc_b.reused_entity_count > 0

    # Fresh world for full rebuild comparison (different idempotency key).
    conn_full, ingestion_full, queries_full, ids_full, binding_full, _, graphs_full = (
        _world()
    )
    _build(
        ingestion_full,
        ids_full,
        binding_full,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="m2-026-full-base",
    )
    started_full = time.perf_counter()
    full_b = _build(
        ingestion_full,
        ids_full,
        binding_full,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="m2-026-rev-b-full",
    )
    full_seconds = time.perf_counter() - started_full
    assert full_b.status is SnapshotStatus.ACTIVE

    full_entities = graphs_full.list_snapshot_entities(
        full_b.snapshot_id, tenant_id=ids_full.tenant_alpha
    )
    full_relations = graphs_full.list_snapshot_relations(
        full_b.snapshot_id, tenant_id=ids_full.tenant_alpha
    )
    inc_entities = graphs.list_snapshot_entities(
        inc_b.snapshot_id, tenant_id=ids.tenant_alpha
    )
    inc_relations = graphs.list_snapshot_relations(
        inc_b.snapshot_id, tenant_id=ids.tenant_alpha
    )
    comparison = compare_normalized_snapshots(
        full_entities, full_relations, inc_entities, inc_relations
    )
    assert comparison.only_left_entities == 0
    assert comparison.only_right_entities == 0
    assert comparison.only_left_relations == 0
    assert comparison.only_right_relations == 0

    query_compare = queries.compare_snapshots(
        scope, rev_a.snapshot_id, inc_b.snapshot_id
    )
    assert (
        query_compare.comparison.only_left_entities
        + query_compare.comparison.only_right_entities
        + query_compare.comparison.only_left_relations
        + query_compare.comparison.only_right_relations
        > 0
    )
    metrics["steps"]["incremental_vs_full"] = {
        "status": "pass",
        "full_seconds": round(full_seconds, 4),
        "incremental_seconds": round(inc_seconds, 4),
        "full_entity_count": full_b.entity_count,
        "full_relation_count": full_b.relation_count,
        "incremental_entity_count": inc_b.entity_count,
        "incremental_relation_count": inc_b.relation_count,
        "reused_entity_count": inc_b.reused_entity_count,
        "rebuilt_entity_count": inc_b.rebuilt_entity_count,
        "reused_relation_count": inc_b.reused_relation_count,
        "rebuilt_relation_count": inc_b.rebuilt_relation_count,
        "equivalence": {
            "matching_entities": comparison.matching_entities,
            "matching_relations": comparison.matching_relations,
            "only_left_entities": comparison.only_left_entities,
            "only_right_entities": comparison.only_right_entities,
            "only_left_relations": comparison.only_left_relations,
            "only_right_relations": comparison.only_right_relations,
        },
    }

    # --- 6. Historical rev_a still queryable after supersede ---
    historical = queries.get_snapshot(
        _scope(ids, binding_id, snapshot_id=rev_a.snapshot_id)
    )
    assert historical.snapshot_id == rev_a.snapshot_id
    assert historical.status is SnapshotStatus.SUPERSEDED
    hist_entities = queries.find_entities(
        _scope(ids, binding_id, snapshot_id=rev_a.snapshot_id),
        path="sample_app/service.py",
        entity_kinds=(EntityKind.CLASS,),
        budget=BUDGET,
    )
    assert any(
        entity.qualified_name == "sample_app.service.Greeter"
        for entity in hist_entities.entities
    )
    assert graphs.list_snapshot_entities(
        rev_a.snapshot_id, tenant_id=ids.tenant_alpha
    )
    metrics["steps"]["historical_rev_a"] = {"status": "pass"}

    # --- 7. Changed-source stale propagation (on a world that still has rev_a) ---
    conn_stale, ingestion_stale, _, ids_stale, binding_stale, intel_stale, _ = _world()
    rev_a_stale = _build(
        ingestion_stale,
        ids_stale,
        binding_stale,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="m2-026-stale-a",
    )
    service_source_id = stable_source_id(
        tenant_id=ids_stale.tenant_alpha,
        workspace_object_id=ids_stale.workspace_alpha_1,
        repository_binding_id=binding_stale,
        repository_relative_path="sample_app/service.py",
    )
    schema_source_id = stable_source_id(
        tenant_id=ids_stale.tenant_alpha,
        workspace_object_id=ids_stale.workspace_alpha_1,
        repository_binding_id=binding_stale,
        repository_relative_path="sample_app/schema.py",
    )
    service_source = intel_stale.get_source(service_source_id)
    schema_source = intel_stale.get_source(schema_source_id)
    assert service_source is not None
    assert schema_source is not None
    dependent = ContextModule(
        module_id=generate_uuidv7(),
        tenant_id=ids_stale.tenant_alpha,
        workspace_object_id=ids_stale.workspace_alpha_1,
        module_key="architecture",
        purpose_text="depends on service.py",
        applicability_text="service changes",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids_stale.human_owner,
        revision=1,
        source_ids=(service_source_id,),
        observation_ids=(service_source.current_observation_id,),
    )
    unrelated = ContextModule(
        module_id=generate_uuidv7(),
        tenant_id=ids_stale.tenant_alpha,
        workspace_object_id=ids_stale.workspace_alpha_1,
        module_key="domain-language",
        purpose_text="depends on schema.py",
        applicability_text="schema changes",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids_stale.human_owner,
        revision=1,
        source_ids=(schema_source_id,),
        observation_ids=(schema_source.current_observation_id,),
    )
    intel_stale.save_context_module(dependent)
    intel_stale.save_context_module(unrelated)
    _build(
        ingestion_stale,
        ids_stale,
        binding_stale,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="m2-026-stale-b",
        base_snapshot_id=rev_a_stale.snapshot_id,
        changed_paths=changed,
    )
    assert (
        intel_stale.get_context_module(dependent.module_id).freshness
        is StaleStatus.STALE
    )
    assert (
        intel_stale.get_context_module(unrelated.module_id).freshness
        is StaleStatus.FRESH
    )
    metrics["steps"]["stale_propagation"] = {"status": "pass"}

    # --- 8a. Partial coverage does not activate ---
    conn_partial, ingestion_partial, _, ids_partial, binding_partial, _, _ = _world()
    partial = _build(
        ingestion_partial,
        ids_partial,
        binding_partial,
        revision=REV_A,
        tree="rev_a",
        idempotency_key="m2-026-partial",
        limits=ExtractionLimits(max_files=1, max_entities=5000),
    )
    assert partial.status is SnapshotStatus.FAILED
    status_partial = ingestion_partial.get_status(
        tenant_id=ids_partial.tenant_alpha,
        workspace_object_id=ids_partial.workspace_alpha_1,
        repository_binding_id=binding_partial,
    )
    assert status_partial.active_snapshot is None
    metrics["steps"]["partial_coverage"] = {"status": "pass"}

    # --- 8b. Revision mismatch fails closed ---
    conn_mismatch, ingestion_mismatch, _, ids_mismatch, binding_mismatch, _, _ = (
        _world()
    )
    mismatch = _build(
        ingestion_mismatch,
        ids_mismatch,
        binding_mismatch,
        revision="fixture:" + ("deadbeef" * 8),
        tree="rev_a",
        idempotency_key="m2-026-mismatch",
    )
    assert mismatch.status is SnapshotStatus.FAILED
    assert M2_EVENT_CODE_GRAPH_BUILD_FAILED in mismatch.event_types
    status_mismatch = ingestion_mismatch.get_status(
        tenant_id=ids_mismatch.tenant_alpha,
        workspace_object_id=ids_mismatch.workspace_alpha_1,
        repository_binding_id=binding_mismatch,
    )
    assert status_mismatch.active_snapshot is None
    metrics["steps"]["revision_mismatch"] = {"status": "pass"}

    # --- 8c. Idempotent replay ---
    replay = _build(
        ingestion,
        ids,
        binding_id,
        revision=REV_B,
        tree="rev_b",
        idempotency_key="m2-026-rev-b-inc",
        base_snapshot_id=rev_a.snapshot_id,
        changed_paths=changed,
    )
    assert replay.replayed is True
    assert replay.snapshot_id == inc_b.snapshot_id
    metrics["steps"]["idempotent_replay"] = {"status": "pass"}

    # --- 9. Event payloads have no prompt/interpretation authority leak ---
    events = _event_payloads(conn, ids.tenant_alpha)
    event_types = {item["event_type"] for item in events}
    assert M2_EVENT_CODE_GRAPH_BUILD_REQUESTED in event_types
    assert M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED in event_types
    assert (
        M2_EVENT_CODE_GRAPH_BUILD_COMPLETED in event_types
        or M2_EVENT_CODE_GRAPH_BUILD_PARTIAL in event_types
    )
    for item in events:
        blob = json.dumps(item["payload"], sort_keys=True).lower()
        for fragment in _FORBIDDEN_EVENT_FRAGMENTS:
            assert fragment not in blob, f"leaked '{fragment}' in {item['event_type']}"
        assert "you are" not in blob
    metrics["steps"]["events"] = {
        "status": "pass",
        "types": sorted(event_types),
    }

    metrics["m2_022_precision_recall_reference"] = (
        "artifacts/m2-022-python-extractor-metrics.json"
    )
    metrics["m2_024_equivalence_reference"] = (
        "artifacts/m2-024-incremental-refresh-metrics.json"
    )
    metrics["residual_risks"] = [
        "contains/defines/imports precision is low vs golden because the "
        "extractor emits structural edges beyond the minimal golden set; "
        "recall on supported kinds remains 1.0.",
        "unresolved_dynamic_call is diagnostic-only and never becomes a CALLS fact.",
        "Impact neighbors receive new observations even when file bytes are unchanged.",
        "Partial coverage cannot activate until a durable policy-decision seam exists.",
        "GitNexus remains research-only (PolyForm NC); not a production dependency.",
    ]

    artifact = ROOT / "artifacts" / "m2-026-acceptance-metrics.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    conn_full.close()
    conn_stale.close()
    conn_partial.close()
    conn_mismatch.close()


def test_m2_026_concurrent_activation_keeps_single_active(tmp_path: Path) -> None:
    """Focused concurrent activation assert (file DB + barrier)."""

    db_path = tmp_path / "m2-026-concurrent.sqlite"
    setup = sqlite3.connect(str(db_path), check_same_thread=False)
    setup.row_factory = sqlite3.Row
    setup.execute("PRAGMA busy_timeout = 5000")
    migrate_governance(setup)
    ids = FixtureIds()
    ensure_default_local_tenant(
        setup, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    auth = SqliteAuthorityRepository(setup)
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
    revisions = SqliteRevisionRepository(setup)
    revisions.register_object(
        GovernanceObject(
            object_id=ids.workspace_alpha_1,
            tenant_id=ids.tenant_alpha,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    collab = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(setup)
    )
    ref = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="git",
        object_type="repository",
        external_object_id="repo-concurrent-026",
        locator="git://example/concurrent-026",
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
        external_repository_id="repo-concurrent-026",
        canonical_locator="git://example/concurrent-026",
        default_branch="main",
        status=WorkspaceBindingStatus.ACTIVE,
        external_reference_id=ref.reference_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    collab.save_repository_binding(binding)
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
    from holodeck_governance.domain.workspace.intelligence import (
        SourceType,
        TrustClass,
        WorkspaceSource,
    )

    intelligence = SqliteWorkspaceIntelligenceRepository(setup)
    source_id = generate_uuidv7()
    observation_id = generate_uuidv7()
    intelligence.register_source(
        WorkspaceSource(
            source_id=source_id,
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            source_type=SourceType.REPOSITORY_FILE,
            locator="sample_app/shared.py",
            observed_revision=REV_A,
            trust_class=TrustClass.ORDINARY_REFERENCE,
            owner_actor_id=ids.human_owner,
            sensitivity="public",
            refresh_policy="on_revision_change",
            observed_at=NOW,
            stale_status=StaleStatus.FRESH,
            created_at=NOW,
            created_by_actor_id=ids.human_owner,
            current_observation_id=observation_id,
        )
    )
    graph = SqliteCodeGraphRepository(setup)
    snapshot_ids: list[str] = []
    for index in range(2):
        run_id = generate_uuidv7()
        entity = CodeEntityFact(
            entity_fact_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding.binding_id,
            entity_key=build_entity_key(
                entity_kind=EntityKind.MODULE,
                repository_relative_path=f"sample_app/mod{index}.py",
                qualified_name=f"sample_app.mod{index}",
            ),
            entity_kind=EntityKind.MODULE,
            repository_relative_path=f"sample_app/mod{index}.py",
            source_id=source_id,
            source_observation_id=observation_id,
            observation_method=ObservationMethod.DIRECT_PARSE,
            created_at=NOW,
            language="python",
            qualified_name=f"sample_app.mod{index}",
        )
        graph.insert_entity_fact(entity)
        snap = RepositoryGraphSnapshot(
            snapshot_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            repository_binding_id=binding.binding_id,
            repository_revision=REV_A,
            extraction_run_id=run_id,
            status=SnapshotStatus.BUILDING,
            created_at=NOW,
            created_by_actor_id=ids.human_owner,
            coverage_status=CoverageStatus.COMPLETE,
            entity_count=1,
            relation_count=0,
            coverage_notes=("m2-026 concurrent fixture",),
        )
        graph.save_building_snapshot(snap)
        graph.save_extraction_run(
            RepositoryExtractionRun(
                extraction_run_id=run_id,
                snapshot_id=snap.snapshot_id,
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
        graph.add_snapshot_entity_memberships(
            snapshot_id=snap.snapshot_id,
            tenant_id=ids.tenant_alpha,
            entity_fact_ids=(entity.entity_fact_id,),
        )
        snapshot_ids.append(snap.snapshot_id)
    setup.close()

    barrier = Barrier(2)
    errors: list[BaseException] = []

    def _activate(snapshot_id: str) -> None:
        local = sqlite3.connect(str(db_path), check_same_thread=False)
        local.row_factory = sqlite3.Row
        local.execute("PRAGMA busy_timeout = 5000")
        repo = SqliteCodeGraphRepository(local)
        try:
            barrier.wait(timeout=5)
            repo.activate_snapshot(
                snapshot_id, tenant_id=ids.tenant_alpha, activated_at=NOW
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            local.close()

    threads = [
        Thread(target=_activate, args=(snapshot_ids[0],)),
        Thread(target=_activate, args=(snapshot_ids[1],)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    verify = sqlite3.connect(str(db_path))
    verify.row_factory = sqlite3.Row
    active = verify.execute(
        """
        SELECT COUNT(*) AS n FROM gov_code_graph_snapshots
        WHERE tenant_id = ? AND repository_binding_id = ? AND status = 'active'
        """,
        (ids.tenant_alpha, binding.binding_id),
    ).fetchone()["n"]
    verify.close()
    assert active == 1
    # At most one activation may fail due to contention; both succeeding is ok
    # only if serialization kept a single active row (asserted above).
    assert len(errors) <= 1
