"""Requirement, test-plan, run, artifact, and evidence records (M1-028)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.records._common import require_ids, require_utc


@dataclass(frozen=True, slots=True)
class RequirementRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    mission_object_id: str
    statement: str
    created_at: datetime
    created_by_actor_id: str
    content_hash: str = ""
    schema_version: str = "m1.requirement.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            mission_object_id=self.mission_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.statement.strip():
            raise MalformedCommandError("requirement invalid")
        require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class TestPlanRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    mission_object_id: str
    summary: str
    created_at: datetime
    created_by_actor_id: str
    content_hash: str = ""
    schema_version: str = "m1.test_plan.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            mission_object_id=self.mission_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.summary.strip():
            raise MalformedCommandError("test plan invalid")
        require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class RunRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    task_object_id: str
    mission_object_id: str
    state: str
    created_at: datetime
    created_by_actor_id: str
    content_hash: str = ""
    schema_version: str = "m1.run.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            task_object_id=self.task_object_id,
            mission_object_id=self.mission_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.state.strip():
            raise MalformedCommandError("run invalid")
        require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    locator: str
    content_hash: str
    created_at: datetime
    created_by_actor_id: str
    schema_version: str = "m1.artifact.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.locator.strip() or not self.content_hash.strip():
            raise MalformedCommandError("artifact invalid")
        require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    record_id: str
    tenant_id: str
    object_id: str
    revision: int
    requirement_object_id: str
    artifact_object_id: str
    content_hash: str
    created_at: datetime
    created_by_actor_id: str
    schema_version: str = "m1.evidence.v1"

    def __post_init__(self) -> None:
        require_ids(
            record_id=self.record_id,
            tenant_id=self.tenant_id,
            object_id=self.object_id,
            requirement_object_id=self.requirement_object_id,
            artifact_object_id=self.artifact_object_id,
            created_by_actor_id=self.created_by_actor_id,
        )
        if self.revision < 1 or not self.content_hash.strip():
            raise MalformedCommandError("evidence invalid")
        require_utc(self.created_at, "created_at")
