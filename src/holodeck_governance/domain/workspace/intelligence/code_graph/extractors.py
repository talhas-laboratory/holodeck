"""Provider-neutral extractor contract assertions (no provider imports)."""

from __future__ import annotations

from holodeck_governance.domain.workspace.intelligence.code_graph.entities import (
    CodeEntityFact,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.relations import (
    CodeRelationFact,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.snapshots import (
    ExtractionDiagnostic,
    assert_relation_endpoints_resolve,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    INITIAL_ENTITY_KINDS,
    INITIAL_RELATION_KINDS,
    CodeGraphReason,
    ObservationMethod,
    RelationKind,
    code_graph_error,
)

# Diagnostic code used when a dynamic call cannot be resolved to a target.
UNRESOLVED_DYNAMIC_CALL: str = "unresolved_dynamic_call"


def assert_entity_catalog_closed(entities: tuple[CodeEntityFact, ...]) -> None:
    for entity in entities:
        if entity.entity_kind not in INITIAL_ENTITY_KINDS:
            raise code_graph_error(
                CodeGraphReason.UNSUPPORTED_FACT_KIND,
                f"unsupported entity kind {entity.entity_kind!r}",
            )


def assert_relation_catalog_closed(relations: tuple[CodeRelationFact, ...]) -> None:
    for relation in relations:
        if relation.relation_kind not in INITIAL_RELATION_KINDS:
            raise code_graph_error(
                CodeGraphReason.UNSUPPORTED_FACT_KIND,
                f"unsupported relation kind {relation.relation_kind!r}",
            )


def assert_no_fabricated_dynamic_call_edges(
    *,
    relations: tuple[CodeRelationFact, ...],
    diagnostics: tuple[ExtractionDiagnostic, ...],
) -> None:
    """Dynamic call sites must appear as diagnostics, never invented CALLS."""

    unresolved_paths = {
        diagnostic.repository_relative_path
        for diagnostic in diagnostics
        if diagnostic.code == UNRESOLVED_DYNAMIC_CALL
        and diagnostic.repository_relative_path is not None
    }
    if not unresolved_paths:
        return
    for relation in relations:
        if relation.relation_kind is not RelationKind.CALLS:
            continue
        if relation.observation_method is ObservationMethod.TOOL_INFERRED:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "tool-inferred CALLS must not substitute for unresolved dynamic calls",
            )


def assert_extraction_candidates_conform(
    *,
    entities: tuple[CodeEntityFact, ...],
    relations: tuple[CodeRelationFact, ...],
    diagnostics: tuple[ExtractionDiagnostic, ...] = (),
) -> None:
    """Reusable conformance gate for every extractor implementation."""

    assert_entity_catalog_closed(entities)
    assert_relation_catalog_closed(relations)
    assert_relation_endpoints_resolve(entities=entities, relations=relations)
    assert_no_fabricated_dynamic_call_edges(
        relations=relations, diagnostics=diagnostics
    )


def relation_kinds_covered(
    relations: tuple[CodeRelationFact, ...],
) -> frozenset[RelationKind]:
    return frozenset(relation.relation_kind for relation in relations)
