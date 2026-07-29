"""Workspace model revision and intent-seed contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.types import (
    REQUIRED_MODEL_SECTIONS,
    ModelRevisionStatus,
    SectionCertainty,
)


@dataclass(frozen=True, slots=True)
class IntentSeed:
    """Initial human intent required before semantic workspace onboarding."""

    purpose_text: str
    primary_users_text: str
    important_risks_text: str
    non_goals_text: str
    decisions_not_automatic_text: str

    def __post_init__(self) -> None:
        for name, value in (
            ("purpose_text", self.purpose_text),
            ("primary_users_text", self.primary_users_text),
            ("important_risks_text", self.important_risks_text),
            ("non_goals_text", self.non_goals_text),
            ("decisions_not_automatic_text", self.decisions_not_automatic_text),
        ):
            if not value.strip():
                raise MalformedCommandError(f"{name} is required")


@dataclass(frozen=True, slots=True)
class ModelSectionState:
    """One required model section with explicit certainty (never invented)."""

    section_key: str
    certainty: SectionCertainty
    summary_hash: str | None = None

    def __post_init__(self) -> None:
        if self.section_key not in REQUIRED_MODEL_SECTIONS:
            raise MalformedCommandError(f"unknown model section {self.section_key}")
        if self.summary_hash is not None and not self.summary_hash.strip():
            raise MalformedCommandError("summary_hash must be non-empty when set")


@dataclass(frozen=True, slots=True)
class WorkspaceModelRevision:
    """Versioned project model; material meaning lives here, not on Workspace."""

    model_revision_id: str
    tenant_id: str
    workspace_object_id: str
    revision: int
    status: ModelRevisionStatus
    intent_seed: IntentSeed
    sections: tuple[ModelSectionState, ...]
    created_at: datetime
    created_by_actor_id: str
    based_on_revision_id: str | None = None
    provenance_reference_ids: tuple[str, ...] = ()
    confidence_summary: str = ""
    approved_by_actor_id: str | None = None
    approved_at: datetime | None = None
    schema_version: str = "m2.workspace_model_revision.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("model_revision_id", self.model_revision_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if self.revision < 1:
            raise MalformedCommandError("revision must be >= 1")
        if self.based_on_revision_id is not None:
            require_opaque_id(self.based_on_revision_id, "based_on_revision_id")
        for ref_id in self.provenance_reference_ids:
            require_opaque_id(ref_id, "provenance_reference_ids")
        present = {section.section_key for section in self.sections}
        missing = [key for key in REQUIRED_MODEL_SECTIONS if key not in present]
        if missing:
            raise MalformedCommandError(
                f"model revision missing required sections: {', '.join(missing)}"
            )
        if len(present) != len(self.sections):
            raise MalformedCommandError("model revision sections must be unique")
        if self.status is ModelRevisionStatus.APPROVED:
            if self.approved_by_actor_id is None or self.approved_at is None:
                raise MalformedCommandError(
                    "approved model revisions require approved_by_actor_id and approved_at"
                )
            require_opaque_id(self.approved_by_actor_id, "approved_by_actor_id")
            require_utc(self.approved_at, "approved_at")
        elif self.approved_by_actor_id is not None or self.approved_at is not None:
            raise MalformedCommandError(
                "approval fields are only valid for approved model revisions"
            )


def section_certainty_map(
    revision: WorkspaceModelRevision,
) -> Mapping[str, SectionCertainty]:
    return {section.section_key: section.certainty for section in revision.sections}
