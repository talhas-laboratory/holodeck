"""Knowledge gaps, contradictions, and workspace decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.types import (
    REQUIRED_MODEL_SECTIONS,
    ContradictionStatus,
    DecisionOutcome,
    GapStatus,
    ReadinessLevel,
)


@dataclass(frozen=True, slots=True)
class KnowledgeGap:
    gap_id: str
    tenant_id: str
    workspace_object_id: str
    question: str
    affected_sections: tuple[str, ...]
    impact_text: str
    risk_if_unresolved_text: str
    status: GapStatus
    created_at: datetime
    created_by_actor_id: str
    owner_actor_id: str | None = None
    resolution_reference_id: str | None = None
    schema_version: str = "m2.knowledge_gap.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("gap_id", self.gap_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        for name, value in (
            ("question", self.question),
            ("impact_text", self.impact_text),
            ("risk_if_unresolved_text", self.risk_if_unresolved_text),
        ):
            if not value.strip():
                raise MalformedCommandError(f"{name} is required")
        if not self.affected_sections:
            raise MalformedCommandError("affected_sections is required")
        for section in self.affected_sections:
            if section not in REQUIRED_MODEL_SECTIONS:
                raise MalformedCommandError(f"unknown affected section {section}")
        if self.owner_actor_id is not None:
            require_opaque_id(self.owner_actor_id, "owner_actor_id")
        if self.status is GapStatus.RESOLVED:
            if self.resolution_reference_id is None:
                raise MalformedCommandError(
                    "resolved gaps require resolution_reference_id"
                )
            require_opaque_id(self.resolution_reference_id, "resolution_reference_id")
        elif self.resolution_reference_id is not None:
            raise MalformedCommandError(
                "resolution_reference_id is only valid for resolved gaps"
            )


@dataclass(frozen=True, slots=True)
class Contradiction:
    contradiction_id: str
    tenant_id: str
    workspace_object_id: str
    claim_reference_ids: tuple[str, ...]
    description: str
    impact_text: str
    status: ContradictionStatus
    created_at: datetime
    created_by_actor_id: str
    resolution_reference_id: str | None = None
    schema_version: str = "m2.contradiction.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("contradiction_id", self.contradiction_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if len(self.claim_reference_ids) < 2:
            raise MalformedCommandError(
                "contradictions require at least two claim references"
            )
        for ref_id in self.claim_reference_ids:
            require_opaque_id(ref_id, "claim_reference_ids")
        if not self.description.strip():
            raise MalformedCommandError("description is required")
        if not self.impact_text.strip():
            raise MalformedCommandError("impact_text is required")
        if self.status is ContradictionStatus.RESOLVED:
            if self.resolution_reference_id is None:
                raise MalformedCommandError(
                    "resolved contradictions require resolution_reference_id"
                )
            require_opaque_id(self.resolution_reference_id, "resolution_reference_id")
        elif self.resolution_reference_id is not None:
            raise MalformedCommandError(
                "resolution_reference_id is only valid for resolved contradictions"
            )


@dataclass(frozen=True, slots=True)
class WorkspaceDecision:
    """Human decision over a workspace model or instruction-authority change."""

    decision_id: str
    tenant_id: str
    workspace_object_id: str
    subject_revision_id: str
    outcome: DecisionOutcome
    rationale: str
    authorized_actor_id: str
    decided_at: datetime
    signed_source_reference_id: str | None = None
    authorized_readiness_level: ReadinessLevel | None = None
    schema_version: str = "m2.workspace_decision.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("decision_id", self.decision_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("subject_revision_id", self.subject_revision_id),
            ("authorized_actor_id", self.authorized_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.decided_at, "decided_at")
        if not self.rationale.strip():
            raise MalformedCommandError("rationale is required")
        if self.signed_source_reference_id is not None:
            require_opaque_id(
                self.signed_source_reference_id, "signed_source_reference_id"
            )
