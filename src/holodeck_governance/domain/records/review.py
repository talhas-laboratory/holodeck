"""Review, approval, decision, and escalation records (M1-029)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.records._common import require_ids, require_utc


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    subject_object_id: str
    subject_revision: int
    created_at: datetime
    created_by_actor_id: str
    status: str = "open"
    content_hash: str = ""
    schema_version: str = "m1.review.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            subject_object_id=self.subject_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or self.subject_revision < 1:
            raise MalformedCommandError("review revisions invalid")
        require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    subject_object_id: str
    subject_revision: int
    created_at: datetime
    created_by_actor_id: str
    decision: str = "approved"
    content_hash: str = ""
    schema_version: str = "m1.approval.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            subject_object_id=self.subject_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or self.subject_revision < 1:
            raise MalformedCommandError("approval revisions invalid")
        require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    subject_object_id: str
    subject_revision: int
    outcome: str
    created_at: datetime
    created_by_actor_id: str
    content_hash: str = ""
    schema_version: str = "m1.decision.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            subject_object_id=self.subject_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or self.subject_revision < 1 or not self.outcome.strip():
            raise MalformedCommandError("decision invalid")
        require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class EscalationRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    subject_object_id: str
    trigger: str
    created_at: datetime
    created_by_actor_id: str
    content_hash: str = ""
    schema_version: str = "m1.escalation.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            subject_object_id=self.subject_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.trigger.strip():
            raise MalformedCommandError("escalation invalid")
        require_utc(self.created_at, "created_at")
