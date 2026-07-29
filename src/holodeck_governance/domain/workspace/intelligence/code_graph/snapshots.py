"""Graph snapshot and extraction-run contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.code_graph.entities import (
    CodeEntityFact,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.paths import (
    require_immutable_repository_revision,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.relations import (
    CodeRelationFact,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    EXTRACTION_RUN_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
    CodeGraphReason,
    CoverageStatus,
    ExtractionRunStatus,
    SnapshotStatus,
    code_graph_error,
)


@dataclass(frozen=True, slots=True)
class ExtractionDiagnostic:
    """Provider-neutral diagnostic recorded with an extraction run."""

    code: str
    message: str
    repository_relative_path: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "diagnostic code and message are required",
            )
        if (
            self.repository_relative_path is not None
            and not self.repository_relative_path.strip()
        ):
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "diagnostic path must be non-empty when set",
            )


@dataclass(frozen=True, slots=True)
class ExtractionLimits:
    """Explicit budgets applied to one extraction run."""

    max_files: int | None = None
    max_file_bytes: int | None = None
    max_entities: int | None = None
    max_relations: int | None = None
    max_seconds: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("max_files", self.max_files),
            ("max_file_bytes", self.max_file_bytes),
            ("max_entities", self.max_entities),
            ("max_relations", self.max_relations),
            ("max_seconds", self.max_seconds),
        ):
            if value is not None and value < 1:
                raise code_graph_error(
                    CodeGraphReason.QUERY_LIMIT,
                    f"{name} must be >= 1 when set",
                )


@dataclass(frozen=True, slots=True)
class RepositoryExtractionRun:
    """One extractor invocation bound to a building or finished snapshot."""

    extraction_run_id: str
    snapshot_id: str
    provider_key: str
    provider_version: str
    provider_schema_version: str
    configuration_hash: str
    requested_revision: str
    actual_revision: str
    started_at: datetime
    status: ExtractionRunStatus
    created_by_actor_id: str
    completed_at: datetime | None = None
    diagnostics: tuple[ExtractionDiagnostic, ...] = ()
    limits: ExtractionLimits = ExtractionLimits()
    schema_version: str = EXTRACTION_RUN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("extraction_run_id", self.extraction_run_id),
            ("snapshot_id", self.snapshot_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.started_at, "started_at")
        if self.completed_at is not None:
            require_utc(self.completed_at, "completed_at")
        for name, value in (
            ("provider_key", self.provider_key),
            ("provider_version", self.provider_version),
            ("provider_schema_version", self.provider_schema_version),
            ("configuration_hash", self.configuration_hash),
        ):
            if not value.strip():
                raise code_graph_error(
                    CodeGraphReason.MALFORMED_FACT, f"{name} is required"
                )
        requested = require_immutable_repository_revision(self.requested_revision)
        actual = require_immutable_repository_revision(self.actual_revision)
        if self.status in (
            ExtractionRunStatus.SUCCEEDED,
            ExtractionRunStatus.PARTIAL,
        ):
            if requested != actual:
                raise code_graph_error(
                    CodeGraphReason.REVISION_MISMATCH,
                    "actual_revision must equal requested_revision before success",
                )
            if self.completed_at is None:
                raise code_graph_error(
                    CodeGraphReason.MALFORMED_FACT,
                    "completed extraction runs require completed_at",
                )
        if self.status is ExtractionRunStatus.RUNNING and self.completed_at is not None:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "running extraction runs must not set completed_at",
            )


@dataclass(frozen=True, slots=True)
class RepositoryGraphSnapshot:
    """Immutable repository graph snapshot membership header."""

    snapshot_id: str
    tenant_id: str
    workspace_object_id: str
    repository_binding_id: str
    repository_revision: str
    status: SnapshotStatus
    extraction_run_id: str
    coverage_status: CoverageStatus
    entity_count: int
    relation_count: int
    created_by_actor_id: str
    created_at: datetime
    base_snapshot_id: str | None = None
    coverage_notes: tuple[str, ...] = ()
    activated_at: datetime | None = None
    schema_version: str = GRAPH_SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("snapshot_id", self.snapshot_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("repository_binding_id", self.repository_binding_id),
            ("extraction_run_id", self.extraction_run_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if self.activated_at is not None:
            require_utc(self.activated_at, "activated_at")
        if self.base_snapshot_id is not None:
            require_opaque_id(self.base_snapshot_id, "base_snapshot_id")
        require_immutable_repository_revision(self.repository_revision)
        if self.entity_count < 0 or self.relation_count < 0:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "entity_count and relation_count must be >= 0",
            )
        for note in self.coverage_notes:
            if not note.strip():
                raise code_graph_error(
                    CodeGraphReason.MALFORMED_FACT,
                    "coverage_notes entries must be non-empty",
                )
        if self.status is SnapshotStatus.ACTIVE:
            if self.activated_at is None:
                raise code_graph_error(
                    CodeGraphReason.MALFORMED_FACT,
                    "active snapshots require activated_at",
                )
            if self.coverage_status is CoverageStatus.UNKNOWN:
                raise code_graph_error(
                    CodeGraphReason.PARTIAL_COVERAGE,
                    "active snapshots cannot have unknown coverage",
                )
        if self.coverage_status is CoverageStatus.PARTIAL and not self.coverage_notes:
            raise code_graph_error(
                CodeGraphReason.PARTIAL_COVERAGE,
                "partial coverage requires explicit coverage_notes",
            )


def assert_relation_endpoints_resolve(
    *,
    entities: tuple[CodeEntityFact, ...],
    relations: tuple[CodeRelationFact, ...],
) -> None:
    """Reject dangling relation endpoints within a candidate fact set."""

    entity_ids = {entity.entity_fact_id for entity in entities}
    for relation in relations:
        if relation.source_entity_fact_id not in entity_ids:
            raise code_graph_error(
                CodeGraphReason.DANGLING_ENDPOINT,
                f"missing source entity {relation.source_entity_fact_id}",
            )
        if relation.target_entity_fact_id not in entity_ids:
            raise code_graph_error(
                CodeGraphReason.DANGLING_ENDPOINT,
                f"missing target entity {relation.target_entity_fact_id}",
            )


def assert_snapshot_counts_match(
    snapshot: RepositoryGraphSnapshot,
    *,
    entities: tuple[CodeEntityFact, ...],
    relations: tuple[CodeRelationFact, ...],
) -> None:
    if snapshot.entity_count != len(entities):
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT,
            "snapshot entity_count must match entity membership",
        )
    if snapshot.relation_count != len(relations):
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT,
            "snapshot relation_count must match relation membership",
        )
