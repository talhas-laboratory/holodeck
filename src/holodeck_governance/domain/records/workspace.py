from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.records._common import require_ids, require_utc
from holodeck_governance.domain.revisions import content_hash_for


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    name: str
    created_at: datetime
    created_by_actor_id: str
    status: str = "active"
    supersedes_revision: int | None = None
    content_hash: str = ""
    schema_version: str = "m1.workspace.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.name.strip():
            raise MalformedCommandError("workspace revision/name invalid")
        require_utc(self.created_at, "created_at")


def hash_workspace(record: WorkspaceRecord) -> str:
    return content_hash_for({"name": record.name, "status": record.status})
