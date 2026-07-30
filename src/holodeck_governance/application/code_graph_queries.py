"""Governed read-only factual code-graph queries and sentinels (M2-025).

Mirrors workspace-intelligence query: no curate permission required. Domain
helpers stay pure; this service scopes, loads bounded snapshot facts via the
store port, and attaches coverage/diagnostics. M3 must consume these DTOs
without importing sqlite or extractor adapters.
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
    MAX_INCREMENTAL_IMPACT_DEPTH,
    NormalizedSnapshotFacts,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    code_graph_error,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.paths import (
    normalize_repository_relative_path,
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
    _traversal_budget,
    change_neighborhood_paths,
    compare_snapshots_facts,
    coverage_from_snapshot,
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
    RelationKind,
)

# Impact neighborhood edges (mirrors domain incremental planner).
_IMPACT_RELATION_KIND_VALUES: tuple[str, ...] = tuple(
    sorted(
        kind.value
        for kind in (
            RelationKind.IMPORTS,
            RelationKind.CALLS,
            RelationKind.INHERITS,
            RelationKind.DEFINES,
            RelationKind.TESTS,
            RelationKind.READS,
            RelationKind.WRITES,
            RelationKind.EXPOSES,
            RelationKind.HANDLES,
            RelationKind.CONFIGURES,
            RelationKind.MIGRATES,
        )
    )
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

    def find_snapshot_entities(
        self,
        snapshot_id: str,
        *,
        tenant_id: str,
        entity_kind: str | None = None,
        entity_kinds: tuple[str, ...] | None = None,
        language: str | None = None,
        qualified_name: str | None = None,
        qualified_name_exact: bool = False,
        entity_fact_ids: tuple[str, ...] | None = None,
        repository_relative_path: str | None = None,
        path_prefix: str | None = None,
        limit: int | None = None,
    ) -> tuple[CodeEntityFact, ...]: ...

    def get_snapshot_entity(
        self, snapshot_id: str, entity_fact_id: str, *, tenant_id: str
    ) -> CodeEntityFact | None: ...

    def find_snapshot_relations(
        self,
        snapshot_id: str,
        *,
        tenant_id: str,
        relation_kinds: tuple[str, ...] | None = None,
        relation_fact_ids: tuple[str, ...] | None = None,
        source_entity_fact_ids: tuple[str, ...] | None = None,
        target_entity_fact_ids: tuple[str, ...] | None = None,
        either_entity_fact_ids: tuple[str, ...] | None = None,
        limit: int | None = None,
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


def _entity_kind_filter_values(
    entity_kinds: tuple[EntityKind, ...],
    budget: QueryBudget,
) -> tuple[str, ...] | None:
    """Intersect caller kinds with budget allowlist; None means no kind filter."""

    kind_allow: set[str] | None = None
    if entity_kinds:
        kind_allow = {kind.value for kind in entity_kinds}
    if budget.entity_kinds:
        budget_kinds = {kind.value for kind in budget.entity_kinds}
        kind_allow = budget_kinds if kind_allow is None else kind_allow & budget_kinds
    if kind_allow is None:
        return None
    return tuple(sorted(kind_allow))


def _snapshot_fact_count(snapshot: RepositoryGraphSnapshot) -> int:
    return snapshot.entity_count + snapshot.relation_count


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
        snapshot, run = self._resolve_snapshot(scope, require_active=False)
        kind_values = _entity_kind_filter_values(entity_kinds, budget)
        omissions: list[str] = []
        if kind_values is not None and not kind_values:
            return FindEntitiesResult(
                entities=(),
                coverage=self._coverage(snapshot),
                omissions=QueryOmissions(reasons=("kind_filtered",)),
                diagnostics=_diagnostic_summary(run),
            )
        path_norm = (
            normalize_repository_relative_path(path) if path is not None else None
        )
        prefix_norm = (
            normalize_repository_relative_path(path_prefix)
            if path_prefix is not None
            else None
        )
        matched = self._graphs.find_snapshot_entities(
            snapshot.snapshot_id,
            tenant_id=scope.tenant_id,
            entity_kinds=kind_values,
            language=language,
            qualified_name=qualified_name,
            repository_relative_path=path_norm,
            path_prefix=prefix_norm,
            limit=budget.max_results + 1,
        )
        if len(matched) > budget.max_results:
            omissions.append("max_results")
            matched = matched[: budget.max_results]
        return FindEntitiesResult(
            entities=matched,
            coverage=self._coverage(snapshot),
            omissions=QueryOmissions(reasons=tuple(dict.fromkeys(omissions))),
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
        snapshot, run = self._resolve_snapshot(scope, require_active=False)
        found = self._graphs.get_snapshot_entity(
            snapshot.snapshot_id,
            entity_fact_id,
            tenant_id=scope.tenant_id,
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
        snapshot, run = self._resolve_snapshot(scope, require_active=False)
        seed = self._graphs.get_snapshot_entity(
            snapshot.snapshot_id,
            entity_fact_id,
            tenant_id=scope.tenant_id,
        )
        if seed is None:
            return NeighborsResult(
                seed_entity_fact_id=entity_fact_id,
                neighbors=(),
                coverage=self._coverage(snapshot),
                omissions=QueryOmissions(),
                diagnostics=_diagnostic_summary(run),
            )
        traversal = _traversal_budget(budget)
        relation_kinds = tuple(kind.value for kind in traversal.relation_kinds)
        fetch_limit = max(traversal.max_results, traversal.max_visited_nodes) + 1
        if direction is TraversalDirection.OUTGOING:
            relations = self._graphs.find_snapshot_relations(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                relation_kinds=relation_kinds,
                source_entity_fact_ids=(entity_fact_id,),
                limit=fetch_limit,
            )
        elif direction is TraversalDirection.INCOMING:
            relations = self._graphs.find_snapshot_relations(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                relation_kinds=relation_kinds,
                target_entity_fact_ids=(entity_fact_id,),
                limit=fetch_limit,
            )
        else:
            relations = self._graphs.find_snapshot_relations(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                relation_kinds=relation_kinds,
                either_entity_fact_ids=(entity_fact_id,),
                limit=fetch_limit,
            )
        endpoint_ids = {entity_fact_id}
        for relation in relations:
            endpoint_ids.add(relation.source_entity_fact_id)
            endpoint_ids.add(relation.target_entity_fact_id)
        entities = self._graphs.find_snapshot_entities(
            snapshot.snapshot_id,
            tenant_id=scope.tenant_id,
            entity_fact_ids=tuple(endpoint_ids),
            limit=len(endpoint_ids),
        )
        neighbors, omissions = neighbors_of(
            seed_entity_fact_id=entity_fact_id,
            entities=entities,
            relations=relations,
            direction=direction,
            budget=traversal,
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
        snapshot, run = self._resolve_snapshot(scope, require_active=False)
        entities, relations = self._collect_traversal_neighborhood(
            scope,
            snapshot,
            seed_entity_fact_id=seed_entity_fact_id,
            direction=direction,
            budget=budget,
        )
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
        snapshot, run = self._resolve_snapshot(scope, require_active=False)
        entities, relations = self._load_change_neighborhood_facts(
            scope, snapshot, changed_paths=tuple(changed_paths), budget=budget
        )
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
        snapshot, run = self._resolve_snapshot(scope, require_active=False)
        entity_ids = tuple(dict.fromkeys(entity_fact_ids))
        relation_ids = tuple(dict.fromkeys(relation_fact_ids))
        entities: tuple[CodeEntityFact, ...] = ()
        if entity_ids:
            entities = self._graphs.find_snapshot_entities(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                entity_fact_ids=entity_ids,
                limit=len(entity_ids),
            )
        relations: tuple[CodeRelationFact, ...] = ()
        if relation_ids:
            relations = self._graphs.find_snapshot_relations(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                relation_fact_ids=relation_ids,
                limit=len(relation_ids),
            )
        provenance = sources_for_facts(
            entities=entities,
            relations=relations,
            entity_fact_ids=entity_ids,
            relation_fact_ids=relation_ids,
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
        notes = tuple(dict.fromkeys((*left.coverage_notes, *right.coverage_notes)))
        coverage = QueryCoverage(
            coverage_status=right.coverage_status,
            notes=notes,
            partial=(
                left.coverage_status.value == "partial"
                or right.coverage_status.value == "partial"
            ),
        )
        total_facts = _snapshot_fact_count(left) + _snapshot_fact_count(right)
        if (
            _snapshot_fact_count(left) > budget.max_visited_nodes
            or _snapshot_fact_count(right) > budget.max_visited_nodes
            or total_facts > budget.max_visited_nodes
        ):
            return CompareSnapshotsResult(
                comparison=NormalizedSnapshotFacts(
                    entity_fingerprints=frozenset(),
                    relation_fingerprints=frozenset(),
                    matching_entities=0,
                    only_left_entities=0,
                    only_right_entities=0,
                    matching_relations=0,
                    only_left_relations=0,
                    only_right_relations=0,
                ),
                coverage=coverage,
                omissions=QueryOmissions(
                    reasons=("comparison_budget_exceeded", "max_visited_nodes")
                ),
                diagnostics=diagnostics,
            )
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
        snapshot, run = self._resolve_snapshot(scope, require_active=False)
        if _snapshot_fact_count(snapshot) > budget.max_visited_nodes:
            return SentinelEvaluationResult(
                findings=(),
                coverage=self._coverage(snapshot),
                omissions=QueryOmissions(reasons=("max_visited_nodes",)),
                diagnostics=_diagnostic_summary(run),
            )
        entities, relations = self._load_sentinel_facts(
            scope,
            snapshot,
            changed_paths=tuple(changed_paths),
            sensitive_path_prefixes=tuple(sensitive_path_prefixes),
            budget=budget,
        )
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

    def _collect_traversal_neighborhood(
        self,
        scope: GraphQueryScope,
        snapshot: RepositoryGraphSnapshot,
        *,
        seed_entity_fact_id: str,
        direction: TraversalDirection,
        budget: QueryBudget,
    ) -> tuple[tuple[CodeEntityFact, ...], tuple[CodeRelationFact, ...]]:
        seed = self._graphs.get_snapshot_entity(
            snapshot.snapshot_id,
            seed_entity_fact_id,
            tenant_id=scope.tenant_id,
        )
        if seed is None:
            return (), ()
        traversal = _traversal_budget(budget)
        relation_kinds = tuple(kind.value for kind in traversal.relation_kinds)
        entities_by_id: dict[str, CodeEntityFact] = {seed.entity_fact_id: seed}
        relations_by_id: dict[str, CodeRelationFact] = {}
        frontier: list[str] = [seed.entity_fact_id]
        visited: set[str] = {seed.entity_fact_id}
        fetch_limit = max(traversal.max_results, traversal.max_visited_nodes) + 1

        for _depth in range(traversal.max_depth):
            if not frontier:
                break
            if len(visited) >= traversal.max_visited_nodes:
                break
            frontier_ids = tuple(frontier)
            if direction is TraversalDirection.OUTGOING:
                batch = self._graphs.find_snapshot_relations(
                    snapshot.snapshot_id,
                    tenant_id=scope.tenant_id,
                    relation_kinds=relation_kinds,
                    source_entity_fact_ids=frontier_ids,
                    limit=fetch_limit,
                )
            elif direction is TraversalDirection.INCOMING:
                batch = self._graphs.find_snapshot_relations(
                    snapshot.snapshot_id,
                    tenant_id=scope.tenant_id,
                    relation_kinds=relation_kinds,
                    target_entity_fact_ids=frontier_ids,
                    limit=fetch_limit,
                )
            else:
                batch = self._graphs.find_snapshot_relations(
                    snapshot.snapshot_id,
                    tenant_id=scope.tenant_id,
                    relation_kinds=relation_kinds,
                    either_entity_fact_ids=frontier_ids,
                    limit=fetch_limit,
                )
            needed: set[str] = set()
            for relation in batch:
                relations_by_id[relation.relation_fact_id] = relation
                needed.add(relation.source_entity_fact_id)
                needed.add(relation.target_entity_fact_id)
            missing = tuple(eid for eid in needed if eid not in entities_by_id)
            if missing:
                loaded = self._graphs.find_snapshot_entities(
                    snapshot.snapshot_id,
                    tenant_id=scope.tenant_id,
                    entity_fact_ids=missing,
                    limit=len(missing),
                )
                for entity in loaded:
                    entities_by_id[entity.entity_fact_id] = entity
            frontier_set = set(frontier_ids)
            next_frontier: list[str] = []
            for relation in batch:
                neighbor_ids: list[str] = []
                if (
                    direction
                    in (
                        TraversalDirection.OUTGOING,
                        TraversalDirection.BOTH,
                    )
                    and relation.source_entity_fact_id in frontier_set
                ):
                    neighbor_ids.append(relation.target_entity_fact_id)
                if (
                    direction
                    in (
                        TraversalDirection.INCOMING,
                        TraversalDirection.BOTH,
                    )
                    and relation.target_entity_fact_id in frontier_set
                ):
                    neighbor_ids.append(relation.source_entity_fact_id)
                for neighbor_id in neighbor_ids:
                    if neighbor_id in visited:
                        continue
                    if len(visited) >= traversal.max_visited_nodes:
                        break
                    neighbor = entities_by_id.get(neighbor_id)
                    if neighbor is None:
                        continue
                    if not traversal.allows_entity_kind(neighbor.entity_kind):
                        continue
                    visited.add(neighbor_id)
                    next_frontier.append(neighbor_id)
            frontier = next_frontier

        return tuple(entities_by_id.values()), tuple(relations_by_id.values())

    def _load_change_neighborhood_facts(
        self,
        scope: GraphQueryScope,
        snapshot: RepositoryGraphSnapshot,
        *,
        changed_paths: tuple[str, ...],
        budget: QueryBudget,
    ) -> tuple[tuple[CodeEntityFact, ...], tuple[CodeRelationFact, ...]]:
        """Load only changed-path entities and impact-expanded neighbors."""

        if _snapshot_fact_count(snapshot) <= budget.max_visited_nodes:
            return self._load_facts_under_budget(scope, snapshot)

        seed_paths = {
            normalize_repository_relative_path(path.strip())
            for path in changed_paths
            if path.strip()
        }
        entities_by_id: dict[str, CodeEntityFact] = {}
        relations_by_id: dict[str, CodeRelationFact] = {}
        for path in seed_paths:
            for entity in self._graphs.find_snapshot_entities(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                repository_relative_path=path,
                limit=budget.max_visited_nodes + 1,
            ):
                entities_by_id[entity.entity_fact_id] = entity

        frontier_paths = set(seed_paths)
        all_paths = set(seed_paths)
        overflow = False
        for _depth in range(MAX_INCREMENTAL_IMPACT_DEPTH):
            if len(entities_by_id) >= budget.max_visited_nodes:
                break
            frontier_ids = tuple(
                entity.entity_fact_id
                for entity in entities_by_id.values()
                if entity.repository_relative_path in frontier_paths
            )
            if not frontier_ids:
                break
            batch = self._graphs.find_snapshot_relations(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                relation_kinds=_IMPACT_RELATION_KIND_VALUES,
                either_entity_fact_ids=frontier_ids,
                limit=budget.max_visited_nodes + 1,
            )
            new_paths: set[str] = set()
            needed: set[str] = set()
            for relation in batch:
                relations_by_id[relation.relation_fact_id] = relation
                needed.add(relation.source_entity_fact_id)
                needed.add(relation.target_entity_fact_id)
            missing = tuple(eid for eid in needed if eid not in entities_by_id)
            if missing:
                for entity in self._graphs.find_snapshot_entities(
                    snapshot.snapshot_id,
                    tenant_id=scope.tenant_id,
                    entity_fact_ids=missing,
                    limit=len(missing),
                ):
                    entities_by_id[entity.entity_fact_id] = entity
                    if entity.repository_relative_path not in all_paths:
                        new_paths.add(entity.repository_relative_path)
            for path in tuple(new_paths):
                for entity in self._graphs.find_snapshot_entities(
                    snapshot.snapshot_id,
                    tenant_id=scope.tenant_id,
                    repository_relative_path=path,
                    limit=budget.max_visited_nodes + 1,
                ):
                    entities_by_id[entity.entity_fact_id] = entity
            if not new_paths:
                break
            all_paths |= new_paths
            frontier_paths = new_paths
        else:
            frontier_ids = tuple(
                entity.entity_fact_id
                for entity in entities_by_id.values()
                if entity.repository_relative_path in frontier_paths
            )
            if frontier_ids:
                batch = self._graphs.find_snapshot_relations(
                    snapshot.snapshot_id,
                    tenant_id=scope.tenant_id,
                    relation_kinds=_IMPACT_RELATION_KIND_VALUES,
                    either_entity_fact_ids=frontier_ids,
                    limit=budget.max_visited_nodes + 1,
                )
                for relation in batch:
                    relations_by_id[relation.relation_fact_id] = relation
                    for endpoint in (
                        relation.source_entity_fact_id,
                        relation.target_entity_fact_id,
                    ):
                        if endpoint not in entities_by_id:
                            overflow = True
                            break
                    if overflow:
                        break

        if overflow:
            # Domain planner would fallback_full; load under budget is impossible.
            # Return collected subset — change_neighborhood_paths may under-expand.
            pass

        return tuple(entities_by_id.values()), tuple(relations_by_id.values())

    def _load_sentinel_facts(
        self,
        scope: GraphQueryScope,
        snapshot: RepositoryGraphSnapshot,
        *,
        changed_paths: tuple[str, ...],
        sensitive_path_prefixes: tuple[str, ...],
        budget: QueryBudget,
    ) -> tuple[tuple[CodeEntityFact, ...], tuple[CodeRelationFact, ...]]:
        """Prefer path-scoped loads; full load only for small in-budget snapshots."""

        if _snapshot_fact_count(snapshot) <= budget.max_visited_nodes:
            return self._load_facts_under_budget(scope, snapshot)

        entities_by_id: dict[str, CodeEntityFact] = {}
        paths = {
            normalize_repository_relative_path(path.strip())
            for path in changed_paths
            if path.strip()
        }
        for path in paths:
            for entity in self._graphs.find_snapshot_entities(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                repository_relative_path=path,
                limit=budget.max_visited_nodes + 1,
            ):
                entities_by_id[entity.entity_fact_id] = entity
        for prefix in sensitive_path_prefixes:
            if not prefix.strip():
                continue
            prefix_norm = normalize_repository_relative_path(prefix.strip())
            for entity in self._graphs.find_snapshot_entities(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                path_prefix=prefix_norm,
                limit=budget.max_visited_nodes + 1,
            ):
                entities_by_id[entity.entity_fact_id] = entity
        if not entities_by_id:
            # No path filters or no matches: cannot evaluate whole oversized graph.
            return (), ()
        entity_ids = tuple(entities_by_id)
        relations = self._graphs.find_snapshot_relations(
            snapshot.snapshot_id,
            tenant_id=scope.tenant_id,
            either_entity_fact_ids=entity_ids,
            limit=budget.max_visited_nodes + 1,
        )
        needed: set[str] = set()
        for relation in relations:
            needed.add(relation.source_entity_fact_id)
            needed.add(relation.target_entity_fact_id)
        missing = tuple(eid for eid in needed if eid not in entities_by_id)
        if missing:
            for entity in self._graphs.find_snapshot_entities(
                snapshot.snapshot_id,
                tenant_id=scope.tenant_id,
                entity_fact_ids=missing,
                limit=len(missing),
            ):
                entities_by_id[entity.entity_fact_id] = entity
        return tuple(entities_by_id.values()), relations

    def _load_facts_under_budget(
        self, scope: GraphQueryScope, snapshot: RepositoryGraphSnapshot
    ) -> tuple[tuple[CodeEntityFact, ...], tuple[CodeRelationFact, ...]]:
        """Full snapshot load for admin/compare/small-fixture paths only."""

        entities = self._graphs.list_snapshot_entities(
            snapshot.snapshot_id, tenant_id=scope.tenant_id
        )
        relations = self._graphs.list_snapshot_relations(
            snapshot.snapshot_id, tenant_id=scope.tenant_id
        )
        return entities, relations

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
