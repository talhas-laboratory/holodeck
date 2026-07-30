from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.records._common import require_ids, require_utc


@dataclass(frozen=True, slots=True)
class TaskRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    workspace_object_id: str
    mission_object_id: str
    title: str
    state: str
    created_at: datetime
    created_by_actor_id: str
    supersedes_revision: int | None = None
    content_hash: str = ""
    schema_version: str = "m1.task.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            workspace_object_id=self.workspace_object_id,
            mission_object_id=self.mission_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.title.strip() or not self.state.strip():
            raise MalformedCommandError("task fields invalid")
        require_utc(self.created_at, "created_at")
