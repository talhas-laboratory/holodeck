"""Bounded factual code-graph query contracts and pure helpers (M2-025).

Operate on in-memory entity/relation tuples. Application services load facts
from storage; this module must not import sqlite, adapters, or extractors.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from holodeck_governance.domain.workspace.intelligence.code_graph.entities import (
    CodeEntityFact,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.incremental import (
    NormalizedSnapshotFacts,
    compare_normalized_snapshots,
    plan_incremental_refresh,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.paths import (
    normalize_repository_relative_path,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.relations import (
    CodeRelationFact,
    build_relation_key,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    INITIAL_ENTITY_KINDS,
    INITIAL_RELATION_KINDS,
    CodeGraphReason,
    CoverageStatus,
    EntityKind,
    RelationKind,
    code_graph_error,
)

# Safe default when a traversal budget omits both entity and relation allowlists.
# Prefer explicit allowlists; this profile avoids expanding CONTAINS directory trees.
DEFAULT_TRAVERSAL_RELATION_KINDS: frozenset[RelationKind] = frozenset(
    {
        RelationKind.IMPORTS,
        RelationKind.CALLS,
        RelationKind.INHERITS,
        RelationKind.TESTS,
        RelationKind.DEFINES,
    }
)


class TraversalDirection(StrEnum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class QueryBudget:
    """Explicit traversal and result limits for one factual query."""

    max_depth: int
    max_results: int
    max_visited_nodes: int
    entity_kinds: tuple[EntityKind, ...] = ()
    relation_kinds: tuple[RelationKind, ...] = ()

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise code_graph_error(
                CodeGraphReason.QUERY_LIMIT, "max_depth must be >= 0"
            )
        if self.max_results < 1:
            raise code_graph_error(
                CodeGraphReason.QUERY_LIMIT, "max_results must be >= 1"
            )
        if self.max_visited_nodes < 1:
            raise code_graph_error(
                CodeGraphReason.QUERY_LIMIT, "max_visited_nodes must be >= 1"
            )
        for kind in self.entity_kinds:
            if kind not in INITIAL_ENTITY_KINDS:
                raise code_graph_error(
                    CodeGraphReason.UNSUPPORTED_FACT_KIND,
                    f"unsupported entity kind {kind!r}",
                )
        for kind in self.relation_kinds:
            if kind not in INITIAL_RELATION_KINDS:
                raise code_graph_error(
                    CodeGraphReason.UNSUPPORTED_FACT_KIND,
                    f"unsupported relation kind {kind!r}",
                )

    def allows_entity_kind(self, kind: EntityKind) -> bool:
        if not self.entity_kinds:
            return True
        return kind in self.entity_kinds

    def allows_relation_kind(self, kind: RelationKind) -> bool:
        if not self.relation_kinds:
            return True
        return kind in self.relation_kinds


def _traversal_budget(budget: QueryBudget) -> QueryBudget:
    """Apply safe defaults for any omitted traversal allowlist independently.

    An empty ``relation_kinds`` never means “all relation kinds.” Entity-only
    budgets still receive the default relation profile.
    """

    from dataclasses import replace

    relation_kinds = budget.relation_kinds
    if not relation_kinds:
        relation_kinds = tuple(
            sorted(DEFAULT_TRAVERSAL_RELATION_KINDS, key=lambda k: k.value)
        )
    if relation_kinds == budget.relation_kinds:
        return budget
    return replace(budget, relation_kinds=relation_kinds)


@dataclass(frozen=True, slots=True)
class GraphPathStep:
    entity_fact_id: str
    relation_fact_id: str | None = None
    relation_kind: RelationKind | None = None


@dataclass(frozen=True, slots=True)
class GraphPath:
    steps: tuple[GraphPathStep, ...]
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class QueryCoverage:
    coverage_status: CoverageStatus
    notes: tuple[str, ...] = ()
    partial: bool = False


@dataclass(frozen=True, slots=True)
class QueryOmissions:
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EntityHit:
    entity: CodeEntityFact


@dataclass(frozen=True, slots=True)
class NeighborHit:
    relation: CodeRelationFact
    neighbor: CodeEntityFact
    direction: TraversalDirection


@dataclass(frozen=True, slots=True)
class ProvenanceHit:
    fact_id: str
    fact_kind: str
    source_id: str
    observation_id: str


@dataclass(frozen=True, slots=True)
class FindEntitiesResult:
    entities: tuple[CodeEntityFact, ...]
    coverage: QueryCoverage
    omissions: QueryOmissions
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GetEntityResult:
    entity: CodeEntityFact | None
    coverage: QueryCoverage
    omissions: QueryOmissions
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NeighborsResult:
    seed_entity_fact_id: str
    neighbors: tuple[NeighborHit, ...]
    coverage: QueryCoverage
    omissions: QueryOmissions
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TraversePathsResult:
    seed_entity_fact_id: str
    paths: tuple[GraphPath, ...]
    coverage: QueryCoverage
    omissions: QueryOmissions
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChangeNeighborhoodResult:
    changed_paths: tuple[str, ...]
    reextract_paths: tuple[str, ...]
    entities: tuple[CodeEntityFact, ...]
    relations: tuple[CodeRelationFact, ...]
    fallback_full: bool
    notes: tuple[str, ...]
    coverage: QueryCoverage
    omissions: QueryOmissions
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourcesForFactsResult:
    provenance: tuple[ProvenanceHit, ...]
    coverage: QueryCoverage
    omissions: QueryOmissions
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CompareSnapshotsResult:
    comparison: NormalizedSnapshotFacts
    coverage: QueryCoverage
    omissions: QueryOmissions
    diagnostics: tuple[str, ...] = ()


def coverage_from_snapshot(
    *,
    coverage_status: CoverageStatus,
    coverage_notes: tuple[str, ...] = (),
) -> QueryCoverage:
    return QueryCoverage(
        coverage_status=coverage_status,
        notes=coverage_notes,
        partial=coverage_status is CoverageStatus.PARTIAL,
    )


def filter_entities(
    entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    *,
    path: str | None = None,
    path_prefix: str | None = None,
    entity_kinds: tuple[EntityKind, ...] | list[EntityKind] = (),
    language: str | None = None,
    qualified_name: str | None = None,
    qualified_name_exact: bool = False,
    budget: QueryBudget,
) -> tuple[tuple[CodeEntityFact, ...], QueryOmissions]:
    """Filter entities with deterministic ``entity_key`` ordering."""

    path_norm = normalize_repository_relative_path(path) if path is not None else None
    prefix_norm = (
        normalize_repository_relative_path(path_prefix)
        if path_prefix is not None
        else None
    )
    kind_allow = frozenset(entity_kinds) if entity_kinds else None
    if budget.entity_kinds:
        budget_kinds = frozenset(budget.entity_kinds)
        kind_allow = budget_kinds if kind_allow is None else kind_allow & budget_kinds

    omissions: list[str] = []
    matched: list[CodeEntityFact] = []
    kind_filtered = False
    for entity in entities:
        if kind_allow is not None and entity.entity_kind not in kind_allow:
            kind_filtered = True
            continue
        if not budget.allows_entity_kind(entity.entity_kind):
            kind_filtered = True
            continue
        if path_norm is not None and entity.repository_relative_path != path_norm:
            continue
        if prefix_norm is not None:
            entity_path = entity.repository_relative_path
            if prefix_norm == ".":
                pass
            elif not (
                entity_path == prefix_norm
                or entity_path.startswith(prefix_norm.rstrip("/") + "/")
            ):
                continue
        if language is not None:
            if entity.language is None or entity.language != language:
                continue
        if qualified_name is not None:
            qn = entity.qualified_name or ""
            if qualified_name_exact:
                if qn != qualified_name:
                    continue
            elif qualified_name not in qn:
                continue
        matched.append(entity)

    matched.sort(key=lambda entity: entity.entity_key)
    if kind_filtered:
        omissions.append("kind_filtered")

    if len(matched) > budget.max_results:
        omissions.append("max_results")
        matched = matched[: budget.max_results]
    return tuple(matched), QueryOmissions(reasons=tuple(dict.fromkeys(omissions)))


def _relation_sort_key(
    relation: CodeRelationFact,
    entities_by_id: dict[str, CodeEntityFact],
) -> tuple[str, str, str]:
    source = entities_by_id.get(relation.source_entity_fact_id)
    target = entities_by_id.get(relation.target_entity_fact_id)
    source_key = (
        source.entity_key if source is not None else relation.source_entity_fact_id
    )
    target_key = (
        target.entity_key if target is not None else relation.target_entity_fact_id
    )
    return (
        build_relation_key(
            relation_kind=relation.relation_kind,
            source_entity_key=source_key,
            target_entity_key=target_key,
            evidence_path=source.repository_relative_path if source else None,
            span=relation.evidence_span,
        ),
        source_key,
        target_key,
    )


def neighbors_of(
    *,
    seed_entity_fact_id: str,
    entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    direction: TraversalDirection,
    budget: QueryBudget,
) -> tuple[tuple[NeighborHit, ...], QueryOmissions]:
    """Return neighbors of one entity under direction and kind budgets."""

    budget = _traversal_budget(budget)
    entities_by_id = {entity.entity_fact_id: entity for entity in entities}
    if seed_entity_fact_id not in entities_by_id:
        return (), QueryOmissions(reasons=())

    candidates: list[tuple[tuple[str, str, str], NeighborHit]] = []
    kind_filtered = False
    for relation in relations:
        if not budget.allows_relation_kind(relation.relation_kind):
            kind_filtered = True
            continue
        hit: NeighborHit | None = None
        if direction in (TraversalDirection.OUTGOING, TraversalDirection.BOTH):
            if relation.source_entity_fact_id == seed_entity_fact_id:
                neighbor = entities_by_id.get(relation.target_entity_fact_id)
                if neighbor is None:
                    continue
                if not budget.allows_entity_kind(neighbor.entity_kind):
                    kind_filtered = True
                    continue
                hit = NeighborHit(
                    relation=relation,
                    neighbor=neighbor,
                    direction=TraversalDirection.OUTGOING,
                )
        if hit is None and direction in (
            TraversalDirection.INCOMING,
            TraversalDirection.BOTH,
        ):
            if relation.target_entity_fact_id == seed_entity_fact_id:
                neighbor = entities_by_id.get(relation.source_entity_fact_id)
                if neighbor is None:
                    continue
                if not budget.allows_entity_kind(neighbor.entity_kind):
                    kind_filtered = True
                    continue
                hit = NeighborHit(
                    relation=relation,
                    neighbor=neighbor,
                    direction=TraversalDirection.INCOMING,
                )
        if hit is None:
            continue
        candidates.append((_relation_sort_key(relation, entities_by_id), hit))

    candidates.sort(key=lambda item: (item[0], item[1].neighbor.entity_key))
    omissions: list[str] = []
    if kind_filtered:
        omissions.append("kind_filtered")

    limited = candidates
    if len(limited) > budget.max_results:
        omissions.append("max_results")
        limited = limited[: budget.max_results]
    if len(limited) > budget.max_visited_nodes:
        omissions.append("max_visited_nodes")
        limited = limited[: budget.max_visited_nodes]

    return (
        tuple(hit for _, hit in limited),
        QueryOmissions(reasons=tuple(dict.fromkeys(omissions))),
    )


def traverse_paths(
    *,
    seed_entity_fact_id: str,
    entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    direction: TraversalDirection,
    budget: QueryBudget,
) -> tuple[tuple[GraphPath, ...], QueryOmissions]:
    """BFS path expansion with deterministic frontier ordering and budgets."""

    budget = _traversal_budget(budget)
    entities_by_id = {entity.entity_fact_id: entity for entity in entities}
    if seed_entity_fact_id not in entities_by_id:
        return (), QueryOmissions(reasons=())

    adjacency: dict[str, list[tuple[CodeRelationFact, str]]] = {}
    kind_filtered = False
    for relation in sorted(
        relations, key=lambda rel: _relation_sort_key(rel, entities_by_id)
    ):
        if not budget.allows_relation_kind(relation.relation_kind):
            kind_filtered = True
            continue
        source = entities_by_id.get(relation.source_entity_fact_id)
        target = entities_by_id.get(relation.target_entity_fact_id)
        if source is None or target is None:
            continue
        if direction in (TraversalDirection.OUTGOING, TraversalDirection.BOTH):
            if budget.allows_entity_kind(target.entity_kind):
                adjacency.setdefault(source.entity_fact_id, []).append(
                    (relation, target.entity_fact_id)
                )
            else:
                kind_filtered = True
        if direction in (TraversalDirection.INCOMING, TraversalDirection.BOTH):
            if budget.allows_entity_kind(source.entity_kind):
                adjacency.setdefault(target.entity_fact_id, []).append(
                    (relation, source.entity_fact_id)
                )
            else:
                kind_filtered = True

    for node_id, edges in list(adjacency.items()):
        edges.sort(
            key=lambda item: (
                _relation_sort_key(item[0], entities_by_id),
                entities_by_id[item[1]].entity_key,
            )
        )
        adjacency[node_id] = edges

    omissions: list[str] = []
    if kind_filtered:
        omissions.append("kind_filtered")

    paths: list[GraphPath] = []
    visited: set[str] = {seed_entity_fact_id}
    queue: deque[tuple[str, tuple[GraphPathStep, ...], int]] = deque(
        [
            (
                seed_entity_fact_id,
                (GraphPathStep(entity_fact_id=seed_entity_fact_id),),
                0,
            )
        ]
    )

    depth_hit = False
    visited_hit = False
    results_hit = False

    while queue:
        if len(paths) >= budget.max_results:
            results_hit = True
            break

        current_id, steps, depth = queue.popleft()
        edges = adjacency.get(current_id, [])

        if depth >= budget.max_depth:
            if edges:
                depth_hit = True
            paths.append(GraphPath(steps=steps, truncated=bool(edges)))
            continue

        if not edges:
            paths.append(GraphPath(steps=steps, truncated=False))
            continue

        enqueued_child = False
        for relation, neighbor_id in edges:
            if neighbor_id in visited:
                continue
            if len(visited) >= budget.max_visited_nodes:
                visited_hit = True
                continue
            if (
                len(paths) + len(queue) + (1 if enqueued_child else 0)
                >= (budget.max_results)
                and not enqueued_child
            ):
                # Still allow enqueueing until result budget is known at emit time.
                pass
            visited.add(neighbor_id)
            next_steps = steps + (
                GraphPathStep(
                    entity_fact_id=neighbor_id,
                    relation_fact_id=relation.relation_fact_id,
                    relation_kind=relation.relation_kind,
                ),
            )
            queue.append((neighbor_id, next_steps, depth + 1))
            enqueued_child = True

        if not enqueued_child:
            truncated = bool(edges) and (
                visited_hit or any(nid not in visited for _, nid in edges)
            )
            if visited_hit:
                truncated = True
            paths.append(GraphPath(steps=steps, truncated=truncated))

    while queue and len(paths) < budget.max_results:
        _current_id, steps, _depth = queue.popleft()
        paths.append(GraphPath(steps=steps, truncated=True))
        results_hit = True

    if queue:
        results_hit = True

    if depth_hit:
        omissions.append("max_depth")
    if visited_hit:
        omissions.append("max_visited_nodes")
    if results_hit:
        omissions.append("max_results")
    paths = paths[: budget.max_results]

    return (
        tuple(paths),
        QueryOmissions(reasons=tuple(dict.fromkeys(omissions))),
    )


def change_neighborhood_paths(
    *,
    changed_paths: tuple[str, ...] | list[str],
    entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    budget: QueryBudget,
) -> tuple[
    tuple[str, ...],
    tuple[CodeEntityFact, ...],
    tuple[CodeRelationFact, ...],
    bool,
    tuple[str, ...],
    QueryOmissions,
]:
    """Expand changed paths via impact planning and collect neighborhood facts."""

    plan = plan_incremental_refresh(
        changed_paths=changed_paths,
        base_entities=entities,
        base_relations=relations,
    )
    reextract = tuple(sorted(plan.reextract_paths))
    path_set = set(reextract)
    matched_entities = [
        entity
        for entity in entities
        if entity.repository_relative_path in path_set
        and budget.allows_entity_kind(entity.entity_kind)
    ]
    matched_entities.sort(key=lambda entity: entity.entity_key)
    entity_ids = {entity.entity_fact_id for entity in matched_entities}

    matched_relations = [
        relation
        for relation in relations
        if budget.allows_relation_kind(relation.relation_kind)
        and relation.source_entity_fact_id in entity_ids
        and relation.target_entity_fact_id in entity_ids
    ]
    entities_by_id = {entity.entity_fact_id: entity for entity in entities}
    matched_relations.sort(key=lambda rel: _relation_sort_key(rel, entities_by_id))

    omissions: list[str] = []
    if any(
        not budget.allows_entity_kind(entity.entity_kind)
        for entity in entities
        if entity.repository_relative_path in path_set
    ) or any(
        not budget.allows_relation_kind(relation.relation_kind)
        for relation in relations
        if relation.source_entity_fact_id in entity_ids
        or relation.target_entity_fact_id in entity_ids
    ):
        # Only record when allowlists actually dropped neighborhood members.
        if budget.entity_kinds or budget.relation_kinds:
            omissions.append("kind_filtered")

    if len(matched_entities) > budget.max_visited_nodes:
        omissions.append("max_visited_nodes")
        matched_entities = matched_entities[: budget.max_visited_nodes]
        entity_ids = {entity.entity_fact_id for entity in matched_entities}
        matched_relations = [
            relation
            for relation in matched_relations
            if relation.source_entity_fact_id in entity_ids
            and relation.target_entity_fact_id in entity_ids
        ]

    if len(matched_entities) + len(matched_relations) > budget.max_results:
        omissions.append("max_results")
        # Prefer keeping entities; trim relations first, then entities.
        remaining = budget.max_results
        if len(matched_entities) > remaining:
            matched_entities = matched_entities[:remaining]
            matched_relations = []
        else:
            remaining -= len(matched_entities)
            matched_relations = matched_relations[:remaining]

    return (
        reextract,
        tuple(matched_entities),
        tuple(matched_relations),
        plan.fallback_full,
        plan.notes,
        QueryOmissions(reasons=tuple(dict.fromkeys(omissions))),
    )


def sources_for_facts(
    *,
    entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    entity_fact_ids: tuple[str, ...] | list[str] = (),
    relation_fact_ids: tuple[str, ...] | list[str] = (),
) -> tuple[ProvenanceHit, ...]:
    """Map requested fact ids to source/observation provenance, sorted."""

    entity_id_set = set(entity_fact_ids)
    relation_id_set = set(relation_fact_ids)
    hits: list[ProvenanceHit] = []
    for entity in entities:
        if entity.entity_fact_id in entity_id_set:
            hits.append(
                ProvenanceHit(
                    fact_id=entity.entity_fact_id,
                    fact_kind="entity",
                    source_id=entity.source_id,
                    observation_id=entity.source_observation_id,
                )
            )
    for relation in relations:
        if relation.relation_fact_id in relation_id_set:
            hits.append(
                ProvenanceHit(
                    fact_id=relation.relation_fact_id,
                    fact_kind="relation",
                    source_id=relation.evidence_source_id,
                    observation_id=relation.evidence_observation_id,
                )
            )
    hits.sort(
        key=lambda hit: (hit.fact_kind, hit.fact_id, hit.source_id, hit.observation_id)
    )
    return tuple(hits)


def compare_snapshots_facts(
    left_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    left_relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    right_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    right_relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    *,
    budget: QueryBudget,
) -> tuple[NormalizedSnapshotFacts, QueryOmissions]:
    """Compare two fact sets under an explicit visit budget."""

    visited = (
        len(left_entities)
        + len(left_relations)
        + len(right_entities)
        + len(right_relations)
    )
    if visited > budget.max_visited_nodes:
        return (
            NormalizedSnapshotFacts(
                entity_fingerprints=frozenset(),
                relation_fingerprints=frozenset(),
                matching_entities=0,
                only_left_entities=0,
                only_right_entities=0,
                matching_relations=0,
                only_left_relations=0,
                only_right_relations=0,
            ),
            QueryOmissions(reasons=("max_visited_nodes",)),
        )
    return (
        compare_normalized_snapshots(
            left_entities,
            left_relations,
            right_entities,
            right_relations,
        ),
        QueryOmissions(),
    )
