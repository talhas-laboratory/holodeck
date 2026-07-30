"""Tenant-bound actors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id


class ActorKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SERVICE = "service"
    IMPORT = "import"


@dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    tenant_id: str
    kind: ActorKind
    display_name: str
    created_at: datetime
    created_by_actor_id: str
    schema_version: str = "m1.actor.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.actor_id, "actor_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if not self.display_name.strip():
            raise MalformedCommandError("display_name is required")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")
