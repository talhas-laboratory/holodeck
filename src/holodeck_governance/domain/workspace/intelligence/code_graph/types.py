"""Factual code-graph vocabulary, schema versions, and stable error reasons."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from holodeck_governance.domain.errors import MalformedCommandError

CODE_GRAPH_SCHEMA_VERSION: Final = "m2.code_graph.v1"
CODE_ENTITY_FACT_SCHEMA_VERSION: Final = "m2.code_entity_fact.v1"
CODE_RELATION_FACT_SCHEMA_VERSION: Final = "m2.code_relation_fact.v1"
GRAPH_SNAPSHOT_SCHEMA_VERSION: Final = "m2.repository_graph_snapshot.v1"
EXTRACTION_RUN_SCHEMA_VERSION: Final = "m2.repository_extraction_run.v1"
ENTITY_KEY_SCHEMA_VERSION: Final = "m2.code_entity_key.v1"
RELATION_KEY_SCHEMA_VERSION: Final = "m2.code_relation_key.v1"

# Versioned catalogs. Unknown kinds are rejected at the domain boundary —
# there is no generic entity/edge escape hatch.
ENTITY_KIND_CATALOG_VERSION: Final = "m2.code_entity_kind.v1"
RELATION_KIND_CATALOG_VERSION: Final = "m2.code_relation_kind.v1"


class EntityKind(StrEnum):
    REPOSITORY = "repository"
    DIRECTORY = "directory"
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    TEST = "test"
    MANIFEST = "manifest"
    CONFIGURATION = "configuration"
    MIGRATION = "migration"
    SCHEMA_OBJECT = "schema_object"
    API_ENTRY_POINT = "api_entry_point"


class RelationKind(StrEnum):
    CONTAINS = "contains"
    DEFINES = "defines"
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    READS = "reads"
    WRITES = "writes"
    EXPOSES = "exposes"
    HANDLES = "handles"
    TESTS = "tests"
    CONFIGURES = "configures"
    MIGRATES = "migrates"


class ObservationMethod(StrEnum):
    DIRECT_PARSE = "direct_parse"
    STATICALLY_RESOLVED = "statically_resolved"
    TOOL_INFERRED = "tool_inferred"
    RUNTIME_OBSERVED = "runtime_observed"


class SnapshotStatus(StrEnum):
    BUILDING = "building"
    ACTIVE = "active"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class ExtractionRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class CoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class CodeGraphReason(StrEnum):
    """Stable reason codes for factual graph contract failures."""

    MALFORMED_FACT = "code_graph.malformed_fact"
    UNSUPPORTED_FACT_KIND = "code_graph.unsupported_fact_kind"
    REVISION_MISMATCH = "code_graph.revision_mismatch"
    PARTIAL_COVERAGE = "code_graph.partial_coverage"
    DANGLING_ENDPOINT = "code_graph.dangling_endpoint"
    QUERY_LIMIT = "code_graph.query_limit"
    ABSOLUTE_PATH = "code_graph.absolute_path"
    MUTABLE_REVISION = "code_graph.mutable_revision"
    INVALID_SPAN = "code_graph.invalid_span"
    INVALID_CONFIDENCE = "code_graph.invalid_confidence"
    INVALID_OBSERVATION_METHOD = "code_graph.invalid_observation_method"


INITIAL_ENTITY_KINDS: Final[frozenset[EntityKind]] = frozenset(EntityKind)
INITIAL_RELATION_KINDS: Final[frozenset[RelationKind]] = frozenset(RelationKind)

# Branch-like names are never valid repository revisions.
REJECTED_REVISION_NAMES: Final[frozenset[str]] = frozenset(
    {
        "head",
        "main",
        "master",
        "develop",
        "trunk",
        "default",
        "origin",
        "upstream",
    }
)


def code_graph_error(reason: CodeGraphReason, detail: str) -> MalformedCommandError:
    """Raise-ready contract error with a stable reason prefix."""

    message = detail.strip() or reason.value
    return MalformedCommandError(f"{reason.value}: {message}")
