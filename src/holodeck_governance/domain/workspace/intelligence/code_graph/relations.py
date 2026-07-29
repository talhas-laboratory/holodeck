"""Code relation fact contracts and deterministic identity keys."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.code_graph.spans import (
    SourceSpan,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    CODE_RELATION_FACT_SCHEMA_VERSION,
    CodeGraphReason,
    INITIAL_RELATION_KINDS,
    ObservationMethod,
    RELATION_KEY_SCHEMA_VERSION,
    RelationKind,
    code_graph_error,
)


def build_relation_key(
    *,
    relation_kind: RelationKind,
    source_entity_key: str,
    target_entity_key: str,
    evidence_path: str | None = None,
    span: SourceSpan | None = None,
) -> str:
    """Build a deterministic relation identity for snapshot reuse checks."""

    if relation_kind not in INITIAL_RELATION_KINDS:
        raise code_graph_error(
            CodeGraphReason.UNSUPPORTED_FACT_KIND,
            f"unsupported relation kind {relation_kind!r}",
        )
    if not source_entity_key.strip() or not target_entity_key.strip():
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT,
            "relation endpoint entity keys are required",
        )
    path = "" if evidence_path is None else evidence_path.strip()
    span_token = ""
    if span is not None:
        span_token = (
            f"{span.start_line}:{span.start_column or 0}-"
            f"{span.end_line}:{span.end_column or 0}"
        )
    return (
        f"{RELATION_KEY_SCHEMA_VERSION}|{relation_kind.value}|"
        f"{source_entity_key}|{target_entity_key}|{path}|{span_token}"
    )


def _require_confidence(
    *,
    observation_method: ObservationMethod,
    confidence: float | None,
) -> None:
    if observation_method is ObservationMethod.TOOL_INFERRED:
        if confidence is None:
            raise code_graph_error(
                CodeGraphReason.INVALID_CONFIDENCE,
                "tool_inferred relations require confidence",
            )
        if not (0.0 < confidence <= 1.0):
            raise code_graph_error(
                CodeGraphReason.INVALID_CONFIDENCE,
                "confidence must be in (0, 1]",
            )
        return
    if confidence is not None:
        raise code_graph_error(
            CodeGraphReason.INVALID_CONFIDENCE,
            "direct or statically resolved relations must not set confidence",
        )


@dataclass(frozen=True, slots=True)
class CodeRelationFact:
    """Immutable observed relation between two entity facts."""

    relation_fact_id: str
    tenant_id: str
    workspace_object_id: str
    repository_binding_id: str
    relation_kind: RelationKind
    source_entity_fact_id: str
    target_entity_fact_id: str
    evidence_source_id: str
    evidence_observation_id: str
    observation_method: ObservationMethod
    created_at: datetime
    evidence_span: SourceSpan | None = None
    confidence: float | None = None
    qualifiers: tuple[str, ...] = ()
    diagnostic: str | None = None
    schema_version: str = CODE_RELATION_FACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("relation_fact_id", self.relation_fact_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("repository_binding_id", self.repository_binding_id),
            ("source_entity_fact_id", self.source_entity_fact_id),
            ("target_entity_fact_id", self.target_entity_fact_id),
            ("evidence_source_id", self.evidence_source_id),
            ("evidence_observation_id", self.evidence_observation_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if self.relation_kind not in INITIAL_RELATION_KINDS:
            raise code_graph_error(
                CodeGraphReason.UNSUPPORTED_FACT_KIND,
                f"unsupported relation kind {self.relation_kind!r}",
            )
        if self.source_entity_fact_id == self.target_entity_fact_id:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "relation endpoints must be distinct entity facts",
            )
        _require_confidence(
            observation_method=self.observation_method,
            confidence=self.confidence,
        )
        if self.observation_method is ObservationMethod.TOOL_INFERRED:
            if self.diagnostic is None or not self.diagnostic.strip():
                raise code_graph_error(
                    CodeGraphReason.INVALID_OBSERVATION_METHOD,
                    "tool_inferred relations require an explicit diagnostic",
                )
        elif self.diagnostic is not None and not self.diagnostic.strip():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "diagnostic must be non-empty when set",
            )
        for qualifier in self.qualifiers:
            if not qualifier.strip():
                raise code_graph_error(
                    CodeGraphReason.MALFORMED_FACT,
                    "qualifiers entries must be non-empty",
                )
