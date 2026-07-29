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

# Context-module keys that count as covering authority concerns for GOVERNED+.
AUTHORITY_COVERING_MODULE_KEYS: frozenset[str] = frozenset(
    {"security-and-authority", "core-principles"}
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


def derive_evidenced_maximum_readiness(
    *,
    has_model: bool,
    model_approved_or_approving: bool,
    has_sources: bool,
    approved_or_approving_module_count: int,
    open_gap_count: int,
    has_governed_authority_basis: bool,
    human_authorized_readiness: ReadinessLevel | None,
) -> ReadinessLevel:
    """Derive the maximum readiness claimable from durable evidence.

    Ladder (deterministic, ascending; never caller-trusted):

    0. No model → ``UNINTERPRETED``.
    1. Model present but not approved (proposed-only): ``DISCOVERED`` when
       sources exist, otherwise ``UNINTERPRETED``.
    2. Approved (or approving) model + ≥1 approved/approving module + no open
       gaps → ``CONTEXTUALIZED``.
    3. Plus a governed authority basis (instruction-authority source and/or an
       authority-covering approved module) **and** a HUMAN-approved readiness
       decision → up to the authorized level, at least ``GOVERNED`` when the
       decision authorizes governed or higher.
    4. ``VERIFIABLE`` / ``OPERATIONALLY_ASSURED`` only when
       ``human_authorized_readiness`` is that level (or higher).

    Open gaps always cap the ladder at ``DISCOVERED`` (governed+ remains
    structurally forbidden while gaps remain open).
    """

    if not has_model:
        return ReadinessLevel.UNINTERPRETED

    if not model_approved_or_approving:
        return (
            ReadinessLevel.DISCOVERED
            if has_sources
            else ReadinessLevel.UNINTERPRETED
        )

    if open_gap_count > 0:
        return ReadinessLevel.DISCOVERED

    if approved_or_approving_module_count < 1:
        return ReadinessLevel.DISCOVERED

    maximum = ReadinessLevel.CONTEXTUALIZED
    if (
        has_governed_authority_basis
        and human_authorized_readiness is not None
        and readiness_level_index(human_authorized_readiness)
        >= readiness_level_index(ReadinessLevel.GOVERNED)
    ):
        maximum = human_authorized_readiness
    return maximum
