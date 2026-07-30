"""Workspace curation proposal validation (activation orchestration is application/storage).

Curators emit structured proposals. Deterministic validation rejects missing IDs,
readiness claims above **derived** evidence, governed+ readiness with open gaps,
and silent trust escalation into instruction authority without a durable human
decision_id. Callers must never trust a self-declared evidenced maximum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.readiness import (
    readiness_at_most,
    readiness_level_index,
)
from holodeck_governance.domain.workspace.intelligence.trust import (
    assert_trust_promotion_allowed,
)
from holodeck_governance.domain.workspace.intelligence.types import (
    ReadinessLevel,
    TrustClass,
)


@dataclass(frozen=True, slots=True)
class TrustPromotion:
    """Explicit source trust change requested by a curation proposal.

    ``decision_id`` is required when the elevation needs a human decision
    (see ``trust_promotion_requires_human_decision``).
    """

    source_id: str
    to_trust: TrustClass
    decision_id: str | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.source_id, "source_id")
        if self.decision_id is not None:
            require_opaque_id(self.decision_id, "decision_id")


@dataclass(frozen=True, slots=True)
class WorkspaceCurationProposal:
    """Structured curator output for model/module/trust/readiness activation.

    Readiness ceilings are derived from durable evidence at validate/activate
    time. Claims at ``GOVERNED`` or higher require ``readiness_decision_id``.
    """

    tenant_id: str
    workspace_object_id: str
    model_revision_id: str
    module_ids_to_approve: tuple[str, ...]
    trust_promotions: tuple[TrustPromotion, ...]
    claimed_readiness_level: ReadinessLevel
    dimensions_checked: tuple[str, ...]
    open_gap_ids: tuple[str, ...]
    policy_basis: str
    evaluator_summary: str
    actor_id: str
    at: datetime
    confidence_summary: str = ""
    assessment_id: str | None = None
    readiness_decision_id: str | None = None
    schema_version: str = "m2.workspace_curation_proposal.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("model_revision_id", self.model_revision_id),
            ("actor_id", self.actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.at, "at")
        if self.assessment_id is not None:
            require_opaque_id(self.assessment_id, "assessment_id")
        if self.readiness_decision_id is not None:
            require_opaque_id(self.readiness_decision_id, "readiness_decision_id")
        for module_id in self.module_ids_to_approve:
            require_opaque_id(module_id, "module_ids_to_approve")
        for gap_id in self.open_gap_ids:
            require_opaque_id(gap_id, "open_gap_ids")
        if (
            readiness_level_index(self.claimed_readiness_level)
            >= readiness_level_index(ReadinessLevel.GOVERNED)
            and self.readiness_decision_id is None
        ):
            raise MalformedCommandError(
                "readiness_decision_id is required for governed or higher claims"
            )


def validate_curation_proposal(
    proposal: WorkspaceCurationProposal,
    *,
    evidenced_maximum: ReadinessLevel,
    current_trust_by_source_id: Mapping[str, TrustClass] | None = None,
) -> None:
    """Reject structurally invalid curation proposals.

    ``evidenced_maximum`` must be derived from durable evidence (see
    ``derive_evidenced_maximum_readiness``), never caller-declared.

    When ``current_trust_by_source_id`` is provided, each promotion is checked
    with ``assert_trust_promotion_allowed``. Without current trust, promotions
    targeting ``instruction_authority`` still require a ``decision_id``.
    """

    for name, value in (
        ("policy_basis", proposal.policy_basis),
        ("evaluator_summary", proposal.evaluator_summary),
    ):
        if not value.strip():
            raise MalformedCommandError(f"{name} is required")
    if not proposal.dimensions_checked:
        raise MalformedCommandError("dimensions_checked is required")
    for dimension in proposal.dimensions_checked:
        if not dimension.strip():
            raise MalformedCommandError("dimensions_checked entries must be non-empty")

    if proposal.open_gap_ids and readiness_level_index(
        proposal.claimed_readiness_level
    ) >= readiness_level_index(ReadinessLevel.GOVERNED):
        raise MalformedCommandError(
            "readiness level governed or higher cannot retain open knowledge gaps"
        )
    readiness_at_most(
        claimed=proposal.claimed_readiness_level,
        evidenced_maximum=evidenced_maximum,
    )

    for promotion in proposal.trust_promotions:
        if current_trust_by_source_id is not None:
            from_trust = current_trust_by_source_id.get(promotion.source_id)
            if from_trust is None:
                raise MalformedCommandError(
                    f"trust promotion references unknown source {promotion.source_id}"
                )
            assert_trust_promotion_allowed(
                from_trust=from_trust,
                to_trust=promotion.to_trust,
                decision_id=promotion.decision_id,
            )
        elif (
            promotion.to_trust is TrustClass.INSTRUCTION_AUTHORITY
            and promotion.decision_id is None
        ):
            raise MalformedCommandError(
                "trust elevation requires an approved human workspace decision_id"
            )
