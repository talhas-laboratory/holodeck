"""Replaceable repository extractor port for factual code-graph observation.

Application and domain layers depend only on these provider-neutral contracts.
Provider SDKs stay inside adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeEntityFact,
    CodeGraphReason,
    CodeRelationFact,
    CoverageStatus,
    ExtractionDiagnostic,
    ExtractionLimits,
    code_graph_error,
    require_immutable_repository_revision,
)


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Identity of one extractor implementation at a pinned version."""

    provider_key: str
    provider_version: str
    provider_schema_version: str
    configuration_hash: str

    def __post_init__(self) -> None:
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


@dataclass(frozen=True, slots=True)
class ExtractorCapabilities:
    """Declared provider capabilities used for selection and readiness."""

    provider: ProviderDescriptor
    languages: tuple[str, ...]
    entity_kinds: tuple[str, ...]
    relation_kinds: tuple[str, ...]
    supports_incremental: bool
    supports_offline: bool
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.languages:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT, "languages is required"
            )
        if not self.entity_kinds or not self.relation_kinds:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "entity_kinds and relation_kinds are required",
            )


@dataclass(frozen=True, slots=True)
class PathSourceBinding:
    """Maps one repository-relative path to registered source observations."""

    repository_relative_path: str
    source_id: str
    source_observation_id: str

    def __post_init__(self) -> None:
        require_opaque_id(self.source_id, "source_id")
        require_opaque_id(self.source_observation_id, "source_observation_id")
        if not self.repository_relative_path.strip():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "repository_relative_path is required",
            )


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    """One fixed-revision extraction request with explicit budgets."""

    repository_path: Path
    tenant_id: str
    workspace_object_id: str
    repository_binding_id: str
    requested_revision: str
    limits: ExtractionLimits
    language_allowlist: tuple[str, ...] = ("python",)
    path_includes: tuple[str, ...] = ()
    path_excludes: tuple[str, ...] = ()
    changed_paths: tuple[str, ...] = ()
    path_source_bindings: tuple[PathSourceBinding, ...] = ()
    base_snapshot_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("repository_binding_id", self.repository_binding_id),
        ):
            require_opaque_id(value, name)
        require_immutable_repository_revision(self.requested_revision)
        if self.base_snapshot_id is not None:
            require_opaque_id(self.base_snapshot_id, "base_snapshot_id")
        if not self.language_allowlist:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT, "language_allowlist is required"
            )
        if not isinstance(self.repository_path, Path):
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT, "repository_path must be a Path"
            )
        # Extraction runs against a local checkout path; absolute host paths are
        # allowed here. Repository-relative paths inside facts remain constrained
        # by the domain path validators.
        if not str(self.repository_path).strip():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT, "repository_path is required"
            )
        if self.limits.max_files is None and self.limits.max_entities is None:
            raise code_graph_error(
                CodeGraphReason.QUERY_LIMIT,
                "extraction requests require at least one of max_files or max_entities",
            )
        for name, values in (
            ("path_includes", self.path_includes),
            ("path_excludes", self.path_excludes),
            ("changed_paths", self.changed_paths),
        ):
            for item in values:
                if not item.strip():
                    raise code_graph_error(
                        CodeGraphReason.MALFORMED_FACT,
                        f"{name} entries must be non-empty",
                    )


@dataclass(frozen=True, slots=True)
class ExtractionCoverage:
    """Coverage claim for one extraction result."""

    status: CoverageStatus
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status is CoverageStatus.PARTIAL and not self.notes:
            raise code_graph_error(
                CodeGraphReason.PARTIAL_COVERAGE,
                "partial coverage requires notes",
            )
        for note in self.notes:
            if not note.strip():
                raise code_graph_error(
                    CodeGraphReason.MALFORMED_FACT,
                    "coverage notes must be non-empty",
                )


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Provider-neutral extraction output before Holodeck persistence."""

    actual_revision: str
    provider: ProviderDescriptor
    candidate_entities: tuple[CodeEntityFact, ...]
    candidate_relations: tuple[CodeRelationFact, ...]
    diagnostics: tuple[ExtractionDiagnostic, ...]
    coverage: ExtractionCoverage

    def __post_init__(self) -> None:
        require_immutable_repository_revision(self.actual_revision)


class RepositoryExtractor(Protocol):
    """Replaceable factual extractor boundary.

    Implementations may use provider tooling internally. They must return only
    Holodeck code-graph contracts and must not claim instruction authority.
    """

    def describe_capabilities(self) -> ExtractorCapabilities:
        """Return pinned provider identity and supported surface."""

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Observe one immutable repository revision under explicit limits."""
