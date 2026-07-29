"""Code entity fact contracts and deterministic identity keys."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.code_graph.paths import (
    normalize_repository_relative_path,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.spans import (
    SourceSpan,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    CODE_ENTITY_FACT_SCHEMA_VERSION,
    ENTITY_KEY_SCHEMA_VERSION,
    CodeGraphReason,
    EntityKind,
    INITIAL_ENTITY_KINDS,
    ObservationMethod,
    code_graph_error,
)


def build_entity_key(
    *,
    entity_kind: EntityKind,
    repository_relative_path: str,
    qualified_name: str | None = None,
) -> str:
    """Build a deterministic entity key within one repository revision.

    Continuity across rename/move is never inferred: a changed path or
    qualified name yields a new key.
    """

    if entity_kind not in INITIAL_ENTITY_KINDS:
        raise code_graph_error(
            CodeGraphReason.UNSUPPORTED_FACT_KIND,
            f"unsupported entity kind {entity_kind!r}",
        )
    path = normalize_repository_relative_path(repository_relative_path)
    name = "" if qualified_name is None else qualified_name.strip()
    if qualified_name is not None and not name:
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT,
            "qualified_name must be non-empty when set",
        )
    return f"{ENTITY_KEY_SCHEMA_VERSION}|{entity_kind.value}|{path}|{name}"


@dataclass(frozen=True, slots=True)
class CodeEntityFact:
    """Immutable observed code entity at one repository revision."""

    entity_fact_id: str
    tenant_id: str
    workspace_object_id: str
    repository_binding_id: str
    entity_key: str
    entity_kind: EntityKind
    repository_relative_path: str
    source_id: str
    source_observation_id: str
    observation_method: ObservationMethod
    created_at: datetime
    language: str | None = None
    qualified_name: str | None = None
    span: SourceSpan | None = None
    content_hash: str | None = None
    extractor_native_id: str | None = None
    schema_version: str = CODE_ENTITY_FACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("entity_fact_id", self.entity_fact_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("repository_binding_id", self.repository_binding_id),
            ("source_id", self.source_id),
            ("source_observation_id", self.source_observation_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if self.entity_kind not in INITIAL_ENTITY_KINDS:
            raise code_graph_error(
                CodeGraphReason.UNSUPPORTED_FACT_KIND,
                f"unsupported entity kind {self.entity_kind!r}",
            )
        path = normalize_repository_relative_path(self.repository_relative_path)
        object.__setattr__(self, "repository_relative_path", path)
        expected = build_entity_key(
            entity_kind=self.entity_kind,
            repository_relative_path=path,
            qualified_name=self.qualified_name,
        )
        if self.entity_key != expected:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "entity_key must match deterministic key construction",
            )
        if self.language is not None and not self.language.strip():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "language must be non-empty when set",
            )
        if self.content_hash is not None and not self.content_hash.strip():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "content_hash must be non-empty when set",
            )
        if (
            self.extractor_native_id is not None
            and not self.extractor_native_id.strip()
        ):
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "extractor_native_id must be non-empty when set",
            )
        if self.observation_method is ObservationMethod.TOOL_INFERRED:
            # Entity facts themselves do not carry confidence; tool-inferred
            # entity observations still require an explicit native id/diagnostic
            # seam via extractor_native_id.
            if self.extractor_native_id is None:
                raise code_graph_error(
                    CodeGraphReason.INVALID_OBSERVATION_METHOD,
                    "tool_inferred entity facts require extractor_native_id",
                )
