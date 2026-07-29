"""Context items and versioned context modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc
from holodeck_governance.domain.workspace.intelligence.types import (
    STANDARD_CONTEXT_MODULE_KEYS,
    ContextItemType,
    ModuleApprovalStatus,
    StaleStatus,
    TrustClass,
    ValidationStatus,
)


@dataclass(frozen=True, slots=True)
class ContextItem:
    """Inspectable fact, claim, instruction, or unknown."""

    item_id: str
    tenant_id: str
    workspace_object_id: str
    item_type: ContextItemType
    statement: str
    trust_class: TrustClass
    validation_status: ValidationStatus
    freshness: StaleStatus
    created_at: datetime
    created_by_actor_id: str
    source_reference_ids: tuple[str, ...] = ()
    confidence: float | None = None
    applicability: str = ""
    conflicts_with_item_ids: tuple[str, ...] = ()
    approved_by_actor_id: str | None = None
    schema_version: str = "m2.context_item.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("item_id", self.item_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if not self.statement.strip():
            raise MalformedCommandError("statement is required")
        for ref_id in self.source_reference_ids:
            require_opaque_id(ref_id, "source_reference_ids")
        for item_id in self.conflicts_with_item_ids:
            require_opaque_id(item_id, "conflicts_with_item_ids")
        if self.approved_by_actor_id is not None:
            require_opaque_id(self.approved_by_actor_id, "approved_by_actor_id")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise MalformedCommandError("confidence must be between 0 and 1")
        if self.item_type is ContextItemType.GENERATED_SUMMARY:
            if self.confidence is None:
                raise MalformedCommandError(
                    "generated summaries require an explicit confidence value"
                )
            if not self.source_reference_ids:
                raise MalformedCommandError(
                    "generated summaries require exact source reference ids"
                )
            if self.trust_class is TrustClass.INSTRUCTION_AUTHORITY:
                raise MalformedCommandError(
                    "generated summaries cannot be instruction authority"
                )
        if (
            self.item_type is ContextItemType.APPROVED_INSTRUCTION
            and self.trust_class is not TrustClass.INSTRUCTION_AUTHORITY
        ):
            raise MalformedCommandError(
                "approved instructions require trust_class=instruction_authority"
            )
        if (
            self.item_type is ContextItemType.APPROVED_INSTRUCTION
            and self.approved_by_actor_id is None
        ):
            raise MalformedCommandError(
                "approved instructions require approved_by_actor_id"
            )


@dataclass(frozen=True, slots=True)
class ContextModule:
    """Versioned, bounded set of context for one concern."""

    module_id: str
    tenant_id: str
    workspace_object_id: str
    module_key: str
    purpose_text: str
    applicability_text: str
    approval_status: ModuleApprovalStatus
    freshness: StaleStatus
    created_at: datetime
    created_by_actor_id: str
    revision: int = 1
    item_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    approved_by_actor_id: str | None = None
    approved_at: datetime | None = None
    schema_version: str = "m2.context_module.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("module_id", self.module_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if self.module_key not in STANDARD_CONTEXT_MODULE_KEYS:
            raise MalformedCommandError(f"unknown context module key {self.module_key}")
        if not self.purpose_text.strip():
            raise MalformedCommandError("purpose_text is required")
        if not self.applicability_text.strip():
            raise MalformedCommandError("applicability_text is required")
        if self.revision < 1:
            raise MalformedCommandError("revision must be >= 1")
        for item_id in self.item_ids:
            require_opaque_id(item_id, "item_ids")
        for source_id in self.source_ids:
            require_opaque_id(source_id, "source_ids")
        for observation_id in self.observation_ids:
            require_opaque_id(observation_id, "observation_ids")
        if self.source_ids and not self.observation_ids:
            raise MalformedCommandError(
                "observation_ids are required when source_ids are present"
            )
        if self.approval_status is ModuleApprovalStatus.APPROVED:
            if self.approved_by_actor_id is None or self.approved_at is None:
                raise MalformedCommandError(
                    "approved modules require approved_by_actor_id and approved_at"
                )
            require_opaque_id(self.approved_by_actor_id, "approved_by_actor_id")
            require_utc(self.approved_at, "approved_at")
        elif self.approved_by_actor_id is not None or self.approved_at is not None:
            raise MalformedCommandError(
                "approval fields are only valid for approved modules"
            )
