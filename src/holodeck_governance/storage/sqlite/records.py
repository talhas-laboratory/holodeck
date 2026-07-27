"""Write repositories for remaining typed record families (M1-027–M1-029)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from holodeck_governance.domain.ids import generate_uuidv7
import json

from holodeck_governance.domain.records.artifact import ArtifactRecord
from holodeck_governance.domain.records.decision import DecisionRecord
from holodeck_governance.domain.records.evidence import EvidenceRecord
from holodeck_governance.domain.records.intent import IntentRecord
from holodeck_governance.domain.records.mission import MissionRecord, hash_mission
from holodeck_governance.domain.records.requirement import RequirementRecord
from holodeck_governance.domain.records.review import (
    ApprovalRecord,
    EscalationRecord,
    ReviewRecord,
)
from holodeck_governance.domain.records.run import RunRecord
from holodeck_governance.domain.records.source import SourceRecord
from holodeck_governance.domain.records.test_plan import TestPlanRecord
from holodeck_governance.domain.records.workspace import WorkspaceRecord, hash_workspace
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.revisions import ObjectRevision, content_hash_for
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository


class SqliteRecordRepository:
    """Persists immutable typed record revisions with registry/head linkage."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        migrate_governance(conn)
        self._revisions = SqliteRevisionRepository(conn)

    def save_workspace(self, record: WorkspaceRecord) -> WorkspaceRecord:
        digest = record.content_hash or hash_workspace(record)
        self._ensure_object(record.object_id, record.tenant_id, "Workspace", record)
        self._conn.execute(
            """
            INSERT INTO gov_workspaces(
                record_id, tenant_id, object_id, revision, name, status,
                content_hash, schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.name,
                record.status,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"name": record.name, "status": record.status},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_source(self, record: SourceRecord) -> SourceRecord:
        digest = record.content_hash or content_hash_for(
            {
                "kind": record.kind,
                "locator": record.locator,
                "workspace_object_id": record.workspace_object_id,
            }
        )
        self._ensure_object(record.object_id, record.tenant_id, "Source", record)
        self._conn.execute(
            """
            INSERT INTO gov_sources(
                record_id, tenant_id, object_id, revision, workspace_object_id,
                kind, locator, provenance_ref, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.workspace_object_id,
                record.kind,
                record.locator,
                record.provenance_ref,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"kind": record.kind, "locator": record.locator},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_intent(self, record: IntentRecord) -> IntentRecord:
        digest = record.content_hash or content_hash_for(
            {
                "statement": record.statement,
                "constraints": dict(record.constraints or {}),
                "non_goals": list(record.non_goals),
            }
        )
        self._ensure_object(record.object_id, record.tenant_id, "Intent", record)
        self._conn.execute(
            """
            INSERT INTO gov_intents(
                record_id, tenant_id, object_id, revision, workspace_object_id,
                statement, constraints_json, non_goals_json, content_hash,
                schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.workspace_object_id,
                record.statement,
                json.dumps(dict(record.constraints or {}), sort_keys=True),
                json.dumps(list(record.non_goals)),
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"statement": record.statement},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_mission(self, record: MissionRecord) -> MissionRecord:
        digest = record.content_hash or hash_mission(record)
        self._ensure_object(record.object_id, record.tenant_id, "Mission", record)
        self._conn.execute(
            """
            INSERT INTO gov_missions(
                record_id, tenant_id, object_id, revision, workspace_object_id,
                intent_object_id, summary, status, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.workspace_object_id,
                record.intent_object_id,
                record.summary,
                record.status,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"summary": record.summary, "status": record.status},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_requirement(self, record: RequirementRecord) -> RequirementRecord:
        digest = record.content_hash or content_hash_for(
            {"statement": record.statement, "mission_object_id": record.mission_object_id}
        )
        self._ensure_object(record.object_id, record.tenant_id, "Requirement", record)
        self._conn.execute(
            """
            INSERT INTO gov_requirements(
                record_id, tenant_id, object_id, revision, mission_object_id,
                statement, content_hash, schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.mission_object_id,
                record.statement,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"statement": record.statement},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_test_plan(self, record: TestPlanRecord) -> TestPlanRecord:
        digest = record.content_hash or content_hash_for(
            {"summary": record.summary, "mission_object_id": record.mission_object_id}
        )
        self._ensure_object(record.object_id, record.tenant_id, "TestPlan", record)
        self._conn.execute(
            """
            INSERT INTO gov_test_plans(
                record_id, tenant_id, object_id, revision, mission_object_id,
                summary, content_hash, schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.mission_object_id,
                record.summary,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"summary": record.summary},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_run(self, record: RunRecord) -> RunRecord:
        digest = record.content_hash or content_hash_for(
            {
                "state": record.state,
                "task_object_id": record.task_object_id,
                "mission_object_id": record.mission_object_id,
            }
        )
        self._ensure_object(record.object_id, record.tenant_id, "Run", record)
        self._conn.execute(
            """
            INSERT INTO gov_runs(
                record_id, tenant_id, object_id, revision, task_object_id,
                mission_object_id, state, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.task_object_id,
                record.mission_object_id,
                record.state,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"state": record.state},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_artifact(self, record: ArtifactRecord) -> ArtifactRecord:
        digest = record.content_hash
        self._ensure_object(record.object_id, record.tenant_id, "Artifact", record)
        self._conn.execute(
            """
            INSERT INTO gov_artifacts(
                record_id, tenant_id, object_id, revision, kind, locator,
                content_hash, schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                "artifact",
                record.locator,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"locator": record.locator},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_evidence(self, record: EvidenceRecord) -> EvidenceRecord:
        digest = record.content_hash
        self._ensure_object(record.object_id, record.tenant_id, "Evidence", record)
        self._conn.execute(
            """
            INSERT INTO gov_evidence(
                record_id, tenant_id, object_id, revision, requirement_object_id,
                artifact_object_id, content_hash, schema_version, created_at,
                created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.requirement_object_id,
                record.artifact_object_id,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {
                "requirement_object_id": record.requirement_object_id,
                "artifact_object_id": record.artifact_object_id,
            },
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_review(self, record: ReviewRecord) -> ReviewRecord:
        digest = record.content_hash or content_hash_for(
            {
                "status": record.status,
                "subject_object_id": record.subject_object_id,
                "subject_revision": record.subject_revision,
            }
        )
        self._ensure_object(record.object_id, record.tenant_id, "Review", record)
        self._conn.execute(
            """
            INSERT INTO gov_reviews(
                record_id, tenant_id, object_id, revision, subject_object_id,
                subject_revision, status, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.subject_object_id,
                record.subject_revision,
                record.status,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"status": record.status},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_approval(self, record: ApprovalRecord) -> ApprovalRecord:
        digest = record.content_hash or content_hash_for(
            {
                "decision": record.decision,
                "subject_object_id": record.subject_object_id,
                "subject_revision": record.subject_revision,
            }
        )
        self._ensure_object(record.object_id, record.tenant_id, "Approval", record)
        self._conn.execute(
            """
            INSERT INTO gov_approvals(
                record_id, tenant_id, object_id, revision, subject_object_id,
                subject_revision, decision, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.subject_object_id,
                record.subject_revision,
                record.decision,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"decision": record.decision},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_decision(
        self, record: DecisionRecord, *, command_id: str | None = None
    ) -> DecisionRecord:
        digest = record.content_hash or content_hash_for(
            {
                "outcome": record.outcome,
                "subject_object_id": record.subject_object_id,
                "subject_revision": record.subject_revision,
            }
        )
        self._ensure_object(record.object_id, record.tenant_id, "Decision", record)
        self._conn.execute(
            """
            INSERT INTO gov_decisions(
                record_id, tenant_id, object_id, revision, subject_object_id,
                subject_revision, outcome, command_id, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.subject_object_id,
                record.subject_revision,
                record.outcome,
                command_id,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"outcome": record.outcome},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def save_escalation(self, record: EscalationRecord) -> EscalationRecord:
        digest = record.content_hash or content_hash_for(
            {
                "trigger": record.trigger,
                "subject_object_id": record.subject_object_id,
            }
        )
        self._ensure_object(record.object_id, record.tenant_id, "Escalation", record)
        self._conn.execute(
            """
            INSERT INTO gov_escalations(
                record_id, tenant_id, object_id, revision, subject_object_id,
                trigger, outbox_item_id, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.tenant_id,
                record.object_id,
                record.revision,
                record.subject_object_id,
                record.trigger,
                None,
                digest,
                record.schema_version,
                record.created_at.isoformat(),
                record.created_by_actor_id,
            ),
        )
        self._append_revision(
            record.object_id,
            record.tenant_id,
            record.revision,
            digest,
            {"trigger": record.trigger},
            record.created_at,
            record.created_by_actor_id,
        )
        return record

    def get_requirement(self, object_id: str, revision: int) -> RequirementRecord | None:
        row = self._conn.execute(
            "SELECT * FROM gov_requirements WHERE object_id = ? AND revision = ?",
            (object_id, revision),
        ).fetchone()
        if row is None:
            return None
        return RequirementRecord(
            record_id=str(row["record_id"]),
            tenant_id=str(row["tenant_id"]),
            object_id=str(row["object_id"]),
            revision=int(row["revision"]),
            mission_object_id=str(row["mission_object_id"]),
            statement=str(row["statement"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            content_hash=str(row["content_hash"]),
            schema_version=str(row["schema_version"]),
        )

    def _ensure_object(
        self, object_id: str, tenant_id: str, object_type: str, record
    ) -> None:
        if self._revisions.get_object(object_id) is None:
            self._revisions.register_object(
                GovernanceObject(
                    object_id=object_id,
                    tenant_id=tenant_id,
                    object_type=object_type,
                    created_at=record.created_at,
                    created_by_actor_id=record.created_by_actor_id,
                )
            )

    def _append_revision(
        self,
        object_id: str,
        tenant_id: str,
        revision: int,
        digest: str,
        payload: dict,
        created_at: datetime,
        actor_id: str,
    ) -> None:
        if self._revisions.get_revision(object_id, revision) is not None:
            return
        rev = ObjectRevision(
            revision_id=generate_uuidv7(),
            tenant_id=tenant_id,
            object_id=object_id,
            revision=revision,
            content_hash=digest,
            payload=payload,
            created_at=created_at,
            created_by_actor_id=actor_id,
            supersedes_revision=revision - 1 if revision > 1 else None,
            finalized=True,
        )
        self._revisions._insert_revision(rev)
        self._revisions._upsert_head(rev)
