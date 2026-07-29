"""Selective source refresh observations and dependent-module helpers (M2-016).

Pure helpers only: no application, storage, sqlite, or adapter imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.workspace.intelligence.context import ContextModule
from holodeck_governance.domain.workspace.intelligence.model import (
    WorkspaceModelRevision,
)
from holodeck_governance.domain.workspace.intelligence.types import (
    ModelRevisionStatus,
)


@dataclass(frozen=True, slots=True)
class SourceRefreshObservation:
    """Observed revision for an existing workspace source.

    Identify the source by ``source_id`` or workspace ``locator`` (exactly one).
    """

    new_observed_revision: str
    source_id: str | None = None
    locator: str | None = None
    content_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.new_observed_revision.strip():
            raise MalformedCommandError("new_observed_revision is required")
        has_id = self.source_id is not None
        has_locator = self.locator is not None
        if has_id == has_locator:
            raise MalformedCommandError(
                "exactly one of source_id or locator is required"
            )
        if self.source_id is not None:
            require_opaque_id(self.source_id, "source_id")
        if self.locator is not None and not self.locator.strip():
            raise MalformedCommandError("locator must be non-empty when set")
        if self.content_hash is not None and not self.content_hash.strip():
            raise MalformedCommandError("content_hash must be non-empty when set")


def module_ids_depending_on_source(
    modules: Sequence[ContextModule], source_id: str
) -> tuple[str, ...]:
    """Return module ids whose ``source_ids`` include ``source_id`` (WIS-004)."""

    require_opaque_id(source_id, "source_id")
    return tuple(
        module.module_id
        for module in modules
        if source_id in module.source_ids
    )


def select_preferred_model_revision(
    revisions: Sequence[WorkspaceModelRevision],
    *,
    model_revision_id: str | None = None,
) -> WorkspaceModelRevision | None:
    """Pick a specific revision, else prefer approved then highest revision number."""

    if model_revision_id is not None:
        require_opaque_id(model_revision_id, "model_revision_id")
        for revision in revisions:
            if revision.model_revision_id == model_revision_id:
                return revision
        return None

    if not revisions:
        return None

    approved = [
        revision
        for revision in revisions
        if revision.status is ModelRevisionStatus.APPROVED
    ]
    pool = approved if approved else list(revisions)
    return max(pool, key=lambda item: item.revision)
