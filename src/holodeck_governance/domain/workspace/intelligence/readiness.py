"""Workspace readiness assessment contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.types import (
    READINESS_LEVEL_ORDER,
    READINESS_PERMITTED_CAPABILITY,
    ReadinessLevel,
)


@dataclass(frozen=True, slots=True)
class WorkspaceReadinessAssessment:
    """Versioned, evidence-backed readiness decision for a model revision."""

    assessment_id: str
    tenant_id: str
    workspace_object_id: str
    model_revision_id: str
    level: ReadinessLevel
    dimensions_checked: tuple[str, ...]
    open_gap_ids: tuple[str, ...]
    policy_basis: str
    evaluator_summary: str
    assessed_at: datetime
    assessed_by_actor_id: str
    schema_version: str = "m2.workspace_readiness_assessment.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("assessment_id", self.assessment_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("model_revision_id", self.model_revision_id),
            ("assessed_by_actor_id", self.assessed_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.assessed_at, "assessed_at")
        if not self.dimensions_checked:
            raise MalformedCommandError("dimensions_checked is required")
        for name, value in (
            ("policy_basis", self.policy_basis),
            ("evaluator_summary", self.evaluator_summary),
        ):
            if not value.strip():
                raise MalformedCommandError(f"{name} is required")
        for gap_id in self.open_gap_ids:
            require_opaque_id(gap_id, "open_gap_ids")
        # Readiness cannot claim governed+ autonomy while material gaps remain open.
        if self.open_gap_ids and readiness_level_index(self.level) >= readiness_level_index(
            ReadinessLevel.GOVERNED
        ):
            raise MalformedCommandError(
                "readiness level governed or higher cannot retain open knowledge gaps"
            )

    @property
    def permitted_capability(self) -> str:
        return READINESS_PERMITTED_CAPABILITY[self.level]


def readiness_level_index(level: ReadinessLevel) -> int:
    return READINESS_LEVEL_ORDER.index(level)


def readiness_at_most(
    *, claimed: ReadinessLevel, evidenced_maximum: ReadinessLevel
) -> None:
    """Reject readiness claims that exceed available evidence/authority."""

    if readiness_level_index(claimed) > readiness_level_index(evidenced_maximum):
        raise MalformedCommandError(
            "readiness cannot exceed the evidence and approved authority available"
        )
