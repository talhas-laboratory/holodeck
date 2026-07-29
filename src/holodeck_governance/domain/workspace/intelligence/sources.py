"""Workspace source registry contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.types import (
    SourceType,
    StaleStatus,
    TrustClass,
)


@dataclass(frozen=True, slots=True)
class WorkspaceSource:
    """Registered input used to form workspace knowledge."""

    source_id: str
    tenant_id: str
    workspace_object_id: str
    source_type: SourceType
    locator: str
    observed_revision: str
    trust_class: TrustClass
    owner_actor_id: str
    sensitivity: str
    refresh_policy: str
    observed_at: datetime
    stale_status: StaleStatus
    created_at: datetime
    created_by_actor_id: str
    instruction_authority: bool = False
    content_hash: str | None = None
    provenance_reference_id: str | None = None
    module_tags: tuple[str, ...] = ()
    schema_version: str = "m2.workspace_source.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("source_id", self.source_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("owner_actor_id", self.owner_actor_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.observed_at, "observed_at")
        require_utc(self.created_at, "created_at")
        for name, value in (
            ("locator", self.locator),
            ("observed_revision", self.observed_revision),
            ("sensitivity", self.sensitivity),
            ("refresh_policy", self.refresh_policy),
        ):
            if not value.strip():
                raise MalformedCommandError(f"{name} is required")
        if self.content_hash is not None and not self.content_hash.strip():
            raise MalformedCommandError("content_hash must be non-empty when set")
        if self.provenance_reference_id is not None:
            require_opaque_id(self.provenance_reference_id, "provenance_reference_id")
        for tag in self.module_tags:
            if not tag.strip():
                raise MalformedCommandError("module_tags entries must be non-empty")
        if self.instruction_authority and self.trust_class is not TrustClass.INSTRUCTION_AUTHORITY:
            raise MalformedCommandError(
                "instruction_authority flag requires trust_class=instruction_authority"
            )
        if (
            self.trust_class is TrustClass.INSTRUCTION_AUTHORITY
            and not self.instruction_authority
        ):
            raise MalformedCommandError(
                "trust_class=instruction_authority requires instruction_authority=True"
            )
        if (
            self.source_type is SourceType.GENERATED_INTERPRETATION
            or self.trust_class is TrustClass.GENERATED_INTERPRETATION
        ) and self.instruction_authority:
            raise MalformedCommandError(
                "generated interpretations cannot be instruction authority"
            )


def workspace_source_dedupe_key(source: WorkspaceSource) -> tuple[str, str, str]:
    return (source.tenant_id, source.workspace_object_id, source.locator)
