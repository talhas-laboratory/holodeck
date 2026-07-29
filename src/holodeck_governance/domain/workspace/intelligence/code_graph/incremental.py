"""Safe incremental code-graph refresh planning and fact merge (M2-024).

Pure domain helpers: no storage, adapter, sqlite, or HTTP imports.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from holodeck_governance.domain.workspace.intelligence.code_graph.entities import (
    CodeEntityFact,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.paths import (
    normalize_repository_relative_path,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.relations import (
    CodeRelationFact,
    build_relation_key,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    EntityKind,
    RelationKind,
)

# Impact neighborhood edges. CONTAINS is excluded so a changed file does not
# pull the entire directory tree into re-extraction.
_IMPACT_RELATION_KINDS: frozenset[RelationKind] = frozenset(
    {
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
    }
)

# Max BFS hops for incremental impact before forcing a full extract.
MAX_INCREMENTAL_IMPACT_DEPTH = 8


@dataclass(frozen=True, slots=True)
class IncrementalRefreshPlan:
    """Conservative re-extraction neighborhood for one revision delta."""

    reextract_paths: frozenset[str]
    fallback_full: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IncrementalMergeStats:
    """Counts for facts reused from a base snapshot versus rebuilt."""

    reused_entities: int
    rebuilt_entities: int
    reused_relations: int
    rebuilt_relations: int


@dataclass(frozen=True, slots=True)
class NormalizedSnapshotFacts:
    """Fingerprint sets for full-versus-incremental equivalence checks."""

    entity_fingerprints: frozenset[str]
    relation_fingerprints: frozenset[str]
    matching_entities: int
    only_left_entities: int
    only_right_entities: int
    matching_relations: int
    only_left_relations: int
    only_right_relations: int


def _impact_neighbors(
    frontier: set[str],
    *,
    entities_by_id: dict[str, CodeEntityFact],
    base_relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
) -> set[str]:
    added: set[str] = set()
    for relation in base_relations:
        if relation.relation_kind not in _IMPACT_RELATION_KINDS:
            continue
        source = entities_by_id.get(relation.source_entity_fact_id)
        target = entities_by_id.get(relation.target_entity_fact_id)
        if source is None or target is None:
            continue
        source_path = source.repository_relative_path
        target_path = target.repository_relative_path
        if source_path in frontier or target_path in frontier:
            if source_path not in frontier:
                added.add(source_path)
            if target_path not in frontier:
                added.add(target_path)
    return added


def plan_incremental_refresh(
    *,
    changed_paths: tuple[str, ...] | list[str] | frozenset[str],
    base_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    base_relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
) -> IncrementalRefreshPlan:
    """Compute the re-extraction path set, or request a full extract fallback."""

    if not changed_paths:
        return IncrementalRefreshPlan(
            reextract_paths=frozenset(),
            fallback_full=True,
            notes=("empty changed_paths; full extraction required",),
        )

    seed: set[str] = set()
    for path in changed_paths:
        seed.add(normalize_repository_relative_path(path))

    entities_by_id = {entity.entity_fact_id: entity for entity in base_entities}
    frontier = set(seed)
    for _ in range(MAX_INCREMENTAL_IMPACT_DEPTH):
        added = _impact_neighbors(
            frontier,
            entities_by_id=entities_by_id,
            base_relations=base_relations,
        )
        if not added:
            break
        frontier |= added
    else:
        # Depth budget exhausted without stabilizing — one more discovery pass.
        overflow = _impact_neighbors(
            frontier,
            entities_by_id=entities_by_id,
            base_relations=base_relations,
        )
        if overflow:
            return IncrementalRefreshPlan(
                reextract_paths=frozenset(),
                fallback_full=True,
                notes=(
                    "impact neighborhood exceeded "
                    f"MAX_INCREMENTAL_IMPACT_DEPTH={MAX_INCREMENTAL_IMPACT_DEPTH}; "
                    "falling back to full extraction",
                ),
            )

    notes: list[str] = []
    if frontier != seed:
        notes.append(
            f"expanded {len(seed)} changed path(s) to {len(frontier)} "
            "re-extraction path(s) via impact relations"
        )
    return IncrementalRefreshPlan(
        reextract_paths=frozenset(frontier),
        fallback_full=False,
        notes=tuple(notes),
    )


def deleted_paths_after_refresh(
    *,
    reextract_paths: frozenset[str] | set[str],
    base_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    merged_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
) -> tuple[str, ...]:
    """Paths in the re-extraction neighborhood present as files in base but not merged."""

    paths = {normalize_repository_relative_path(path) for path in reextract_paths}
    base_file_paths = {
        entity.repository_relative_path
        for entity in base_entities
        if entity.entity_kind is EntityKind.FILE
        and entity.repository_relative_path in paths
    }
    present_paths = {entity.repository_relative_path for entity in merged_entities}
    return tuple(sorted(base_file_paths - present_paths))


def merge_incremental_facts(
    *,
    base_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    base_relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    extracted_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    extracted_relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    reextract_paths: frozenset[str] | set[str],
) -> tuple[
    tuple[CodeEntityFact, ...],
    tuple[CodeRelationFact, ...],
    IncrementalMergeStats,
]:
    """Merge base facts with a neighborhood extract for ``reextract_paths``."""

    paths = {normalize_repository_relative_path(path) for path in reextract_paths}

    reused_entities: list[CodeEntityFact] = []
    for entity in base_entities:
        if entity.repository_relative_path not in paths:
            reused_entities.append(entity)

    rebuilt_entities: list[CodeEntityFact] = []
    for entity in extracted_entities:
        if entity.repository_relative_path in paths:
            rebuilt_entities.append(entity)

    entity_by_id: dict[str, CodeEntityFact] = {}
    for entity in reused_entities:
        entity_by_id[entity.entity_fact_id] = entity
    for entity in rebuilt_entities:
        entity_by_id[entity.entity_fact_id] = entity

    reused_ids = {entity.entity_fact_id for entity in reused_entities}
    rebuilt_ids = {entity.entity_fact_id for entity in rebuilt_entities}
    final_ids = reused_ids | rebuilt_ids
    final_by_key = {entity.entity_key: entity for entity in entity_by_id.values()}
    extract_id_to_key = {
        entity.entity_fact_id: entity.entity_key for entity in extracted_entities
    }

    reused_relations: list[CodeRelationFact] = []
    for relation in base_relations:
        if (
            relation.source_entity_fact_id in reused_ids
            and relation.target_entity_fact_id in reused_ids
        ):
            reused_relations.append(relation)

    rebuilt_relations: list[CodeRelationFact] = []
    for relation in extracted_relations:
        source_id = _resolve_endpoint_to_final(
            relation.source_entity_fact_id,
            final_ids=final_ids,
            extract_id_to_key=extract_id_to_key,
            final_by_key=final_by_key,
        )
        target_id = _resolve_endpoint_to_final(
            relation.target_entity_fact_id,
            final_ids=final_ids,
            extract_id_to_key=extract_id_to_key,
            final_by_key=final_by_key,
        )
        if source_id is None or target_id is None:
            continue
        # Skip extract edges that only touch reused endpoints — base already
        # carries those (e.g. scaffold CONTAINS between directories).
        if source_id in reused_ids and target_id in reused_ids:
            continue
        if (
            source_id == relation.source_entity_fact_id
            and target_id == relation.target_entity_fact_id
        ):
            rebuilt_relations.append(relation)
        else:
            rebuilt_relations.append(
                replace(
                    relation,
                    source_entity_fact_id=source_id,
                    target_entity_fact_id=target_id,
                )
            )

    entities_out: dict[str, CodeEntityFact] = {}
    for entity in (*reused_entities, *rebuilt_entities):
        entities_out[entity.entity_fact_id] = entity

    relations_out: dict[str, CodeRelationFact] = {}
    for relation in (*reused_relations, *rebuilt_relations):
        relations_out[relation.relation_fact_id] = relation

    stats = IncrementalMergeStats(
        reused_entities=len(reused_ids),
        rebuilt_entities=len(rebuilt_ids),
        reused_relations=len(reused_relations),
        rebuilt_relations=len(rebuilt_relations),
    )
    return (
        tuple(entities_out[key] for key in sorted(entities_out)),
        tuple(relations_out[key] for key in sorted(relations_out)),
        stats,
    )


def compare_normalized_snapshots(
    left_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    left_relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    right_entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    right_relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    *,
    entity_key_fn=None,
) -> NormalizedSnapshotFacts:
    """Compare two fact sets by normalized entity/relation identity keys."""

    key_for_entity = entity_key_fn or (lambda entity: entity.entity_key)

    left_entity_fps = frozenset(key_for_entity(entity) for entity in left_entities)
    right_entity_fps = frozenset(key_for_entity(entity) for entity in right_entities)

    left_entity_by_id = {entity.entity_fact_id: entity for entity in left_entities}
    right_entity_by_id = {entity.entity_fact_id: entity for entity in right_entities}

    left_relation_fps = frozenset(
        _relation_fingerprint(relation, left_entity_by_id)
        for relation in left_relations
    )
    right_relation_fps = frozenset(
        _relation_fingerprint(relation, right_entity_by_id)
        for relation in right_relations
    )

    matching_entities = left_entity_fps & right_entity_fps
    matching_relations = left_relation_fps & right_relation_fps
    return NormalizedSnapshotFacts(
        entity_fingerprints=matching_entities,
        relation_fingerprints=matching_relations,
        matching_entities=len(matching_entities),
        only_left_entities=len(left_entity_fps - right_entity_fps),
        only_right_entities=len(right_entity_fps - left_entity_fps),
        matching_relations=len(matching_relations),
        only_left_relations=len(left_relation_fps - right_relation_fps),
        only_right_relations=len(right_relation_fps - left_relation_fps),
    )


def _resolve_endpoint_to_final(
    endpoint_fact_id: str,
    *,
    final_ids: set[str],
    extract_id_to_key: dict[str, str],
    final_by_key: dict[str, CodeEntityFact],
) -> str | None:
    if endpoint_fact_id in final_ids:
        return endpoint_fact_id
    entity_key = extract_id_to_key.get(endpoint_fact_id)
    if entity_key is None:
        return None
    mapped = final_by_key.get(entity_key)
    if mapped is None:
        return None
    return mapped.entity_fact_id


def _relation_fingerprint(
    relation: CodeRelationFact,
    entities_by_id: dict[str, CodeEntityFact],
) -> str:
    source = entities_by_id[relation.source_entity_fact_id]
    target = entities_by_id[relation.target_entity_fact_id]
    evidence_path = source.repository_relative_path
    return build_relation_key(
        relation_kind=relation.relation_kind,
        source_entity_key=source.entity_key,
        target_entity_key=target.entity_key,
        evidence_path=evidence_path,
        span=relation.evidence_span,
    )
