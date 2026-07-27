"""Typed governance-object registry entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id


@dataclass(frozen=True, slots=True)
class GovernanceObject:
    """Registry row for any typed governed object endpoint."""

    object_id: str
    tenant_id: str
    object_type: str
    created_at: datetime
    created_by_actor_id: str
    schema_version: str = "m1.governance_object.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.object_id, "object_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if not self.object_type.strip():
            raise MalformedCommandError("object_type is required")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")
