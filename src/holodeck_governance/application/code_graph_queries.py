"""Governed read-only factual code-graph queries and sentinels (M2-025).

Mirrors workspace-intelligence query: no curate permission required. Domain
helpers stay pure; this service only scopes, loads snapshot facts, and attaches
coverage/diagnostics. M3 must consume these DTOs without importing sqlite or
extractor adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    MalformedCommandError,
    NotFoundGovernanceError,
)
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.workspace import (
    RepositoryBinding,
    WorkspaceBindingStatus,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeEntityFact,
    CodeGraphReason,
    CodeRelationFact,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    code_graph_error,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.queries import (
    ChangeNeighborhoodResult,
    CompareSnapshotsResult,
    FindEntitiesResult,
    GetEntityResult,
    NeighborsResult,
    QueryBudget,
    QueryCoverage,
    QueryOmissions,
    SourcesForFactsResult,
    TraversalDirection,
    TraversePathsResult,
    change_neighborhood_paths,
    compare_snapshots_facts,
    coverage_from_snapshot,
    filter_entities,
    neighbors_of,
    sources_for_facts,
    traverse_paths,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.readiness import (
    FactualGraphReadiness,
    evaluate_factual_graph_readiness,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.sentinels import (
    SentinelFinding,
    evaluate_sentinels,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    EntityKind,
)


@dataclass(frozen=True, slots=True)
class GraphQueryScope:
    """Mandatory tenant / workspace / binding scope for factual queries."""

    tenant_id: str
    workspace_object_id: str
    repository_binding_id: str
    snapshot_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("repository_binding_id", self.repository_binding_id),
        ):
            require_opaque_id(value, name)
        if self.snapshot_id is not None:
            require_opaque_id(self.snapshot_id, "snapshot_id")


@dataclass(frozen=True, slots=True)
class SentinelEvaluationResult:
    findings: tuple[SentinelFinding, ...]
    coverage: QueryCoverage
    omissions: QueryOmissions
    diagnostics: tuple[str, ...] = ()


class CollaborationBindingPort(Protocol):
    def get_repository_binding(self, binding_id: str) -> RepositoryBinding | None: ...


class IntelligenceWorkspacePort(Protocol):
    def require_workspace_object(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> None: ...


class CodeGraphQueryStorePort(Protocol):
    def get_snapshot(self, snapshot_id: str) -> RepositoryGraphSnapshot | None: ...

    def get_active_snapshot(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        repository_binding_id: str,
    ) -> RepositoryGraphSnapshot | None: ...

    def get_extraction_run(
        self, extraction_run_id: str
    ) -> RepositoryExtractionRun | None: ...

    def list_snapshot_entities(
        self, snapshot_id: str, *, tenant_id: str
    ) -> tuple[CodeEntityFact, ...]: ...

    def list_snapshot_relations(
        self, snapshot_id: str, *, tenant_id: str
    ) -> tuple[CodeRelationFact, ...]: ...

    def require_snapshot(
        self, snapshot_id: str, *, tenant_id: str
    ) -> RepositoryGraphSnapshot: ...


@dataclass(frozen=True, slots=True)
class GraphReadinessView:
    readiness: FactualGraphReadiness
    active_snapshot: RepositoryGraphSnapshot | None
    active_run: RepositoryExtractionRun | None


def _require_budget(budget: QueryBudget | None) -> QueryBudget:
    if budget is None:
        raise code_graph_error(
            CodeGraphReason.QUERY_LIMIT,
            "query budget is required",
        )
    return budget


def _diagnostic_summary(run: RepositoryExtractionRun | None) -> tuple[str, ...]:
    if run is None:
        return ()
    return tuple(
        f"{diagnostic.code}:{diagnostic.message}" for diagnostic in run.diagnostics
    )


class CodeGraphQueryService:
    """Read-only bounded factual queries over activated or historical snapshots."""

    def __init__(
        self,
        *,
        collaboration: CollaborationBindingPort,
        intelligence: IntelligenceWorkspacePort,
        graphs: CodeGraphQueryStorePort,
    ) -> None:
        self._collaboration = collaboration
        self._intelligence = intelligence
        self._graphs = graphs

    def get_active_snapshot(self, scope: GraphQueryScope) -> RepositoryGraphSnapshot:
        snapshot, _run = self._resolve_snapshot(scope, require_active=True)
        return snapshot

    def get_snapshot(self, scope: GraphQueryScope) -> RepositoryGraphSnapshot:
        snapshot, _run = self._resolve_snapshot(scope, require_active=False)
        return snapshot

    def get_graph_readiness(
        self,
        scope: GraphQueryScope,
        *,
        binding_repository_revision: str | None = None,
    ) -> GraphReadinessView:
        """Factual graph readiness dimension (not workspace readiness)."""

        self._require_scope_binding(scope)
        active = self._graphs.get_active_snapshot(
            tenant_id=scope.tenant_id,
            workspace_object_id=scope.workspace_object_id,
            repository_binding_id=scope.repository_binding_id,
        )
        run = None
        if active is not None:
            run = self._graphs.get_extraction_run(active.extraction_run_id)
        readiness = evaluate_factual_graph_readiness(
            active_snapshot=active,
            active_run=run,
            binding_repository_revision=binding_repository_revision,
        )
        return GraphReadinessView(
            readiness=readiness,
            active_snapshot=active,
            active_run=run,
        )

    def find_entities(
        self,
        scope: GraphQueryScope,
        *,
        path: str | None = None,
        path_prefix: str | None = None,
        entity_kinds: tuple[EntityKind, ...] = (),
        language: str | None = None,
        qualified_name: str | None = None,
        budget: QueryBudget,
    ) -> FindEntitiesResult:
        budget = _require_budget(budget)
        snapshot, run, entities, _relations = self._load_facts(scope)
        matched, omissions = filter_entities(
            entities,
            path=path,
            path_prefix=path_prefix,
            entity_kinds=entity_kinds,
            language=language,
            qualified_name=qualified_name,
            budget=budget,
        )
        return FindEntitiesResult(
            entities=matched,
            coverage=self._coverage(snapshot),
            omissions=omissions,
            diagnostics=_diagnostic_summary(run),
        )

    def get_entity(
        self,
        scope: GraphQueryScope,
        entity_fact_id: str,
        budget: QueryBudget,
    ) -> GetEntityResult:
        require_opaque_id(entity_fact_id, "entity_fact_id")
        budget = _require_budget(budget)
        snapshot, run, entities, _relations = self._load_facts(scope)
        found = next(
            (entity for entity in entities if entity.entity_fact_id == entity_fact_id),
            None,
        )
        return GetEntityResult(
            entity=found,
            coverage=self._coverage(snapshot),
            omissions=QueryOmissions(),
            diagnostics=_diagnostic_summary(run),
        )

    def get_neighbors(
        self,
        scope: GraphQueryScope,
        entity_fact_id: str,
        *,
        direction: TraversalDirection,
        budget: QueryBudget,
    ) -> NeighborsResult:
        require_opaque_id(entity_fact_id, "entity_fact_id")
        budget = _require_budget(budget)
        snapshot, run, entities, relations = self._load_facts(scope)
        neighbors, omissions = neighbors_of(
            seed_entity_fact_id=entity_fact_id,
            entities=entities,
            relations=relations,
            direction=direction,
            budget=budget,
        )
        return NeighborsResult(
            seed_entity_fact_id=entity_fact_id,
            neighbors=neighbors,
            coverage=self._coverage(snapshot),
            omissions=omissions,
            diagnostics=_diagnostic_summary(run),
        )

    def traverse_paths(
        self,
        scope: GraphQueryScope,
        seed_entity_fact_id: str,
        *,
        direction: TraversalDirection,
        budget: QueryBudget,
    ) -> TraversePathsResult:
        require_opaque_id(seed_entity_fact_id, "seed_entity_fact_id")
        budget = _require_budget(budget)
        snapshot, run, entities, relations = self._load_facts(scope)
        paths, omissions = traverse_paths(
            seed_entity_fact_id=seed_entity_fact_id,
            entities=entities,
            relations=relations,
            direction=direction,
            budget=budget,
        )
        return TraversePathsResult(
            seed_entity_fact_id=seed_entity_fact_id,
            paths=paths,
            coverage=self._coverage(snapshot),
            omissions=omissions,
            diagnostics=_diagnostic_summary(run),
        )

    def get_change_neighborhood(
        self,
        scope: GraphQueryScope,
        changed_paths: tuple[str, ...] | list[str],
        *,
        budget: QueryBudget,
    ) -> ChangeNeighborhoodResult:
        budget = _require_budget(budget)
        if not changed_paths:
            raise code_graph_error(
                CodeGraphReason.QUERY_LIMIT,
                "changed_paths must be non-empty for change neighborhood",
            )
        snapshot, run, entities, relations = self._load_facts(scope)
        (
            reextract,
            neighborhood_entities,
            neighborhood_relations,
            fallback_full,
            notes,
            omissions,
        ) = change_neighborhood_paths(
            changed_paths=tuple(changed_paths),
            entities=entities,
            relations=relations,
            budget=budget,
        )
        return ChangeNeighborhoodResult(
            changed_paths=tuple(
                sorted({path.strip() for path in changed_paths if path.strip()})
            ),
            reextract_paths=reextract,
            entities=neighborhood_entities,
            relations=neighborhood_relations,
            fallback_full=fallback_full,
            notes=notes,
            coverage=self._coverage(snapshot),
            omissions=omissions,
            diagnostics=_diagnostic_summary(run),
        )

    def get_sources_for_facts(
        self,
        scope: GraphQueryScope,
        entity_fact_ids: tuple[str, ...] | list[str] = (),
        relation_fact_ids: tuple[str, ...] | list[str] = (),
        *,
        budget: QueryBudget,
    ) -> SourcesForFactsResult:
        budget = _require_budget(budget)
        snapshot, run, entities, relations = self._load_facts(scope)
        provenance = sources_for_facts(
            entities=entities,
            relations=relations,
            entity_fact_ids=tuple(entity_fact_ids),
            relation_fact_ids=tuple(relation_fact_ids),
        )
        omissions = QueryOmissions()
        if len(provenance) > budget.max_results:
            provenance = provenance[: budget.max_results]
            omissions = QueryOmissions(reasons=("max_results",))
        return SourcesForFactsResult(
            provenance=provenance,
            coverage=self._coverage(snapshot),
            omissions=omissions,
            diagnostics=_diagnostic_summary(run),
        )

    def compare_snapshots(
        self,
        scope: GraphQueryScope,
        left_snapshot_id: str,
        right_snapshot_id: str,
        *,
        budget: QueryBudget,
    ) -> CompareSnapshotsResult:
        require_opaque_id(left_snapshot_id, "left_snapshot_id")
        require_opaque_id(right_snapshot_id, "right_snapshot_id")
        budget = _require_budget(budget)
        self._require_scope_binding(scope)
        left = self._require_scoped_snapshot(scope, left_snapshot_id)
        right = self._require_scoped_snapshot(scope, right_snapshot_id)
        left_entities = self._graphs.list_snapshot_entities(
            left.snapshot_id, tenant_id=scope.tenant_id
        )
        left_relations = self._graphs.list_snapshot_relations(
            left.snapshot_id, tenant_id=scope.tenant_id
        )
        right_entities = self._graphs.list_snapshot_entities(
            right.snapshot_id, tenant_id=scope.tenant_id
        )
        right_relations = self._graphs.list_snapshot_relations(
            right.snapshot_id, tenant_id=scope.tenant_id
        )
        comparison, omissions = compare_snapshots_facts(
            left_entities,
            left_relations,
            right_entities,
            right_relations,
            budget=budget,
        )
        # Coverage reflects the right (typically newer) snapshot; notes merge both.
        notes = tuple(dict.fromkeys((*left.coverage_notes, *right.coverage_notes)))
        coverage = QueryCoverage(
            coverage_status=right.coverage_status,
            notes=notes,
            partial=(
                left.coverage_status.value == "partial"
                or right.coverage_status.value == "partial"
            ),
        )
        left_run = self._graphs.get_extraction_run(left.extraction_run_id)
        right_run = self._graphs.get_extraction_run(right.extraction_run_id)
        diagnostics = tuple(
            dict.fromkeys(
                (
                    *_diagnostic_summary(left_run),
                    *_diagnostic_summary(right_run),
                )
            )
        )
        return CompareSnapshotsResult(
            comparison=comparison,
            coverage=coverage,
            omissions=omissions,
            diagnostics=diagnostics,
        )

    def evaluate_sentinels(
        self,
        scope: GraphQueryScope,
        *,
        changed_paths: tuple[str, ...] | list[str] = (),
        ownership_tags: tuple[str, ...] | list[str] = (),
        sensitive_path_prefixes: tuple[str, ...] | list[str] = (),
        sensitive_symbols: tuple[str, ...] | list[str] = (),
        budget: QueryBudget,
    ) -> SentinelEvaluationResult:
        budget = _require_budget(budget)
        snapshot, run, entities, relations = self._load_facts(scope)
        findings = evaluate_sentinels(
            entities=entities,
            relations=relations,
            coverage_status=snapshot.coverage_status,
            changed_paths=tuple(changed_paths),
            ownership_tags=tuple(ownership_tags),
            sensitive_path_prefixes=tuple(sensitive_path_prefixes),
            sensitive_symbols=tuple(sensitive_symbols),
        )
        omissions = QueryOmissions()
        if len(findings) > budget.max_results:
            findings = findings[: budget.max_results]
            omissions = QueryOmissions(reasons=("max_results",))
        return SentinelEvaluationResult(
            findings=findings,
            coverage=self._coverage(snapshot),
            omissions=omissions,
            diagnostics=_diagnostic_summary(run),
        )

    def _coverage(self, snapshot: RepositoryGraphSnapshot) -> QueryCoverage:
        return coverage_from_snapshot(
            coverage_status=snapshot.coverage_status,
            coverage_notes=snapshot.coverage_notes,
        )

    def _load_facts(
        self, scope: GraphQueryScope
    ) -> tuple[
        RepositoryGraphSnapshot,
        RepositoryExtractionRun | None,
        tuple[CodeEntityFact, ...],
        tuple[CodeRelationFact, ...],
    ]:
        snapshot, run = self._resolve_snapshot(scope, require_active=False)
        entities = self._graphs.list_snapshot_entities(
            snapshot.snapshot_id, tenant_id=scope.tenant_id
        )
        relations = self._graphs.list_snapshot_relations(
            snapshot.snapshot_id, tenant_id=scope.tenant_id
        )
        return snapshot, run, entities, relations

    def _resolve_snapshot(
        self, scope: GraphQueryScope, *, require_active: bool
    ) -> tuple[RepositoryGraphSnapshot, RepositoryExtractionRun | None]:
        self._require_scope_binding(scope)
        if scope.snapshot_id is not None:
            if require_active:
                raise MalformedCommandError(
                    "get_active_snapshot does not accept an explicit snapshot_id"
                )
            snapshot = self._require_scoped_snapshot(scope, scope.snapshot_id)
        else:
            snapshot = self._graphs.get_active_snapshot(
                tenant_id=scope.tenant_id,
                workspace_object_id=scope.workspace_object_id,
                repository_binding_id=scope.repository_binding_id,
            )
            if snapshot is None:
                raise NotFoundGovernanceError("no active code-graph snapshot")
            self._assert_snapshot_scope(scope, snapshot)
        run = self._graphs.get_extraction_run(snapshot.extraction_run_id)
        return snapshot, run

    def _require_scope_binding(self, scope: GraphQueryScope) -> RepositoryBinding:
        self._intelligence.require_workspace_object(
            scope.workspace_object_id, tenant_id=scope.tenant_id
        )
        binding = self._collaboration.get_repository_binding(
            scope.repository_binding_id
        )
        if binding is None:
            raise NotFoundGovernanceError("repository binding not found")
        if binding.tenant_id != scope.tenant_id:
            raise CrossTenantAccessError("repository binding tenant mismatch")
        if binding.workspace_object_id != scope.workspace_object_id:
            raise MalformedCommandError(
                "repository binding does not belong to workspace"
            )
        if binding.status is not WorkspaceBindingStatus.ACTIVE:
            raise MalformedCommandError(
                "repository binding must be active for graph queries"
            )
        return binding

    def _require_scoped_snapshot(
        self, scope: GraphQueryScope, snapshot_id: str
    ) -> RepositoryGraphSnapshot:
        snapshot = self._graphs.get_snapshot(snapshot_id)
        if snapshot is None:
            raise NotFoundGovernanceError(f"unknown snapshot {snapshot_id}")
        if snapshot.tenant_id != scope.tenant_id:
            raise CrossTenantAccessError("snapshot tenant mismatch")
        self._assert_snapshot_scope(scope, snapshot)
        return snapshot

    def _assert_snapshot_scope(
        self, scope: GraphQueryScope, snapshot: RepositoryGraphSnapshot
    ) -> None:
        if snapshot.tenant_id != scope.tenant_id:
            raise CrossTenantAccessError("snapshot tenant mismatch")
        if snapshot.workspace_object_id != scope.workspace_object_id:
            raise MalformedCommandError("snapshot does not belong to workspace")
        if snapshot.repository_binding_id != scope.repository_binding_id:
            raise MalformedCommandError(
                "snapshot does not belong to repository binding"
            )
