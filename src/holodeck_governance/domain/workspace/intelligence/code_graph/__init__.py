"""Provider-neutral factual code-graph domain contracts.

Must not import application, storage, adapters, sqlite3, HTTP, MCP, or
extractor provider SDKs.
"""

from __future__ import annotations

from holodeck_governance.domain.workspace.intelligence.code_graph.entities import (
    CodeEntityFact,
    build_entity_key,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.extractors import (
    UNRESOLVED_DYNAMIC_CALL,
    assert_entity_catalog_closed,
    assert_extraction_candidates_conform,
    assert_no_fabricated_dynamic_call_edges,
    assert_relation_catalog_closed,
    relation_kinds_covered,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.paths import (
    normalize_repository_relative_path,
    require_immutable_repository_revision,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.relations import (
    CodeRelationFact,
    build_relation_key,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.snapshots import (
    ExtractionDiagnostic,
    ExtractionLimits,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    assert_relation_endpoints_resolve,
    assert_snapshot_counts_match,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.spans import (
    SourceSpan,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    CODE_ENTITY_FACT_SCHEMA_VERSION,
    CODE_GRAPH_SCHEMA_VERSION,
    CODE_RELATION_FACT_SCHEMA_VERSION,
    ENTITY_KEY_SCHEMA_VERSION,
    ENTITY_KIND_CATALOG_VERSION,
    EXTRACTION_RUN_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
    INITIAL_ENTITY_KINDS,
    INITIAL_RELATION_KINDS,
    RELATION_KEY_SCHEMA_VERSION,
    RELATION_KIND_CATALOG_VERSION,
    CodeGraphReason,
    CoverageStatus,
    EntityKind,
    ExtractionRunStatus,
    ObservationMethod,
    RelationKind,
    SnapshotStatus,
    code_graph_error,
)

__all__ = [
    "CODE_ENTITY_FACT_SCHEMA_VERSION",
    "CODE_GRAPH_SCHEMA_VERSION",
    "CODE_RELATION_FACT_SCHEMA_VERSION",
    "ENTITY_KEY_SCHEMA_VERSION",
    "ENTITY_KIND_CATALOG_VERSION",
    "EXTRACTION_RUN_SCHEMA_VERSION",
    "GRAPH_SNAPSHOT_SCHEMA_VERSION",
    "INITIAL_ENTITY_KINDS",
    "INITIAL_RELATION_KINDS",
    "RELATION_KEY_SCHEMA_VERSION",
    "RELATION_KIND_CATALOG_VERSION",
    "UNRESOLVED_DYNAMIC_CALL",
    "CodeEntityFact",
    "CodeGraphReason",
    "CodeRelationFact",
    "CoverageStatus",
    "EntityKind",
    "ExtractionDiagnostic",
    "ExtractionLimits",
    "ExtractionRunStatus",
    "ObservationMethod",
    "RelationKind",
    "RepositoryExtractionRun",
    "RepositoryGraphSnapshot",
    "SnapshotStatus",
    "SourceSpan",
    "assert_entity_catalog_closed",
    "assert_extraction_candidates_conform",
    "assert_no_fabricated_dynamic_call_edges",
    "assert_relation_catalog_closed",
    "assert_relation_endpoints_resolve",
    "assert_snapshot_counts_match",
    "build_entity_key",
    "build_relation_key",
    "code_graph_error",
    "normalize_repository_relative_path",
    "relation_kinds_covered",
    "require_immutable_repository_revision",
]
