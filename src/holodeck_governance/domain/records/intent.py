from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.records._common import require_ids, require_utc


@dataclass(frozen=True, slots=True)
class IntentRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    workspace_object_id: str
    statement: str
    created_at: datetime
    created_by_actor_id: str
    constraints: Mapping[str, str] | None = None
    non_goals: tuple[str, ...] = ()
    supersedes_revision: int | None = None
    content_hash: str = ""
    schema_version: str = "m1.intent.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            workspace_object_id=self.workspace_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.statement.strip():
            raise MalformedCommandError("intent fields invalid")
        require_utc(self.created_at, "created_at")
