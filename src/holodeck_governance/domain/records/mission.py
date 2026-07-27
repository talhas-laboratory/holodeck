from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.records._common import require_ids, require_utc
from holodeck_governance.domain.revisions import content_hash_for


@dataclass(frozen=True, slots=True)
class MissionRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    workspace_object_id: str
    intent_object_id: str
    summary: str
    created_at: datetime
    created_by_actor_id: str
    status: str = "draft"
    supersedes_revision: int | None = None
    content_hash: str = ""
    schema_version: str = "m1.mission.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            workspace_object_id=self.workspace_object_id,
            intent_object_id=self.intent_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.summary.strip():
            raise MalformedCommandError("mission fields invalid")
        require_utc(self.created_at, "created_at")


def hash_mission(record: MissionRecord) -> str:
    return content_hash_for(
        {
            "workspace_object_id": record.workspace_object_id,
            "intent_object_id": record.intent_object_id,
            "summary": record.summary,
            "status": record.status,
        }
    )
