"""Persisted task records and governed state transitions."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from holodeck_governance.domain.errors import NotFoundGovernanceError, StaleRevisionError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records.task import TaskRecord
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.revisions import ObjectRevision, content_hash_for
from holodeck_governance.domain.tenant import assert_same_tenant
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository


class SqliteTaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        migrate_governance(conn)
        self._revisions = SqliteRevisionRepository(conn)

    def create_task(self, task: TaskRecord) -> TaskRecord:
        payload = {
            "title": task.title,
            "state": task.state,
            "workspace_object_id": task.workspace_object_id,
            "mission_object_id": task.mission_object_id,
        }
        digest = task.content_hash or content_hash_for(payload)
        if self._revisions.get_object(task.object_id) is None:
            self._revisions.register_object(
                GovernanceObject(
                    object_id=task.object_id,
                    tenant_id=task.tenant_id,
                    object_type="Task",
                    created_at=task.created_at,
                    created_by_actor_id=task.created_by_actor_id,
                )
            )
        self._insert_task_row(task, digest)
        if self._revisions.get_revision(task.object_id, task.revision) is None:
            revision = ObjectRevision(
                revision_id=generate_uuidv7(),
                tenant_id=task.tenant_id,
                object_id=task.object_id,
                revision=task.revision,
                content_hash=digest,
                payload=payload,
                created_at=task.created_at,
                created_by_actor_id=task.created_by_actor_id,
                supersedes_revision=task.supersedes_revision,
                finalized=True,
            )
            self._revisions._insert_revision(revision)
            self._revisions._upsert_head(revision)
        return task

    def get_head_task(self, object_id: str) -> TaskRecord | None:
        head = self._revisions.get_head(object_id)
        if head is None:
            return None
        return self.get_task(object_id, head.head_revision)

    def get_task(self, object_id: str, revision: int) -> TaskRecord | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_tasks
            WHERE object_id = ? AND revision = ?
            """,
            (object_id, revision),
        ).fetchone()
        return _row_to_task(row) if row else None

    def require_tenant_task(
        self, *, object_id: str, tenant_id: str
    ) -> TaskRecord:
        obj = self._revisions.get_object(object_id)
        if obj is None:
            raise NotFoundGovernanceError(f"unknown object {object_id}")
        if obj.object_type != "Task":
            raise NotFoundGovernanceError(f"object {object_id} is not a Task")
        assert_same_tenant(
            actor_tenant_id=tenant_id,
            record_tenant_id=obj.tenant_id,
            context="task",
        )
        task = self.get_head_task(object_id)
        if task is None:
            raise NotFoundGovernanceError(f"task {object_id} has no head record")
        return task

    def apply_transition(
        self,
        *,
        current: TaskRecord,
        to_state: str,
        actor_id: str,
        created_at: datetime,
        expected_revision: int | None,
    ) -> TaskRecord:
        # Re-read head under the caller's write lock (BEGIN IMMEDIATE UoW).
        head = self.get_head_task(current.object_id)
        if head is None:
            raise StaleRevisionError(f"task {current.object_id} has no head")
        if expected_revision is not None and head.revision != expected_revision:
            raise StaleRevisionError(
                f"expected revision {expected_revision}, head is {head.revision}"
            )
        if head.revision != current.revision:
            raise StaleRevisionError(
                f"stale task view {current.revision}, head is {head.revision}"
            )
        next_revision = head.revision + 1
        payload = {
            "title": head.title,
            "state": to_state,
            "workspace_object_id": head.workspace_object_id,
            "mission_object_id": head.mission_object_id,
        }
        digest = content_hash_for(payload)
        new_task = TaskRecord(
            record_id=generate_uuidv7(),
            tenant_id=head.tenant_id,
            object_id=head.object_id,
            revision=next_revision,
            workspace_object_id=head.workspace_object_id,
            mission_object_id=head.mission_object_id,
            title=head.title,
            state=to_state,
            created_at=created_at,
            created_by_actor_id=actor_id,
            supersedes_revision=head.revision,
            content_hash=digest,
        )
        try:
            self._insert_task_row(new_task, digest)
            revision = ObjectRevision(
                revision_id=generate_uuidv7(),
                tenant_id=new_task.tenant_id,
                object_id=new_task.object_id,
                revision=new_task.revision,
                content_hash=digest,
                payload=payload,
                created_at=created_at,
                created_by_actor_id=actor_id,
                supersedes_revision=head.revision,
                finalized=True,
            )
            self._revisions._insert_revision(revision)
            self._revisions._upsert_head(revision)
        except sqlite3.IntegrityError as exc:
            raise StaleRevisionError(
                f"concurrent task transition lost for {current.object_id}"
            ) from exc
        return new_task

    def _insert_task_row(self, task: TaskRecord, digest: str) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_tasks(
                record_id, tenant_id, object_id, revision, workspace_object_id,
                mission_object_id, title, state, content_hash, schema_version,
                created_at, created_by_actor_id, supersedes_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.record_id,
                task.tenant_id,
                task.object_id,
                task.revision,
                task.workspace_object_id,
                task.mission_object_id,
                task.title,
                task.state,
                digest,
                task.schema_version,
                task.created_at.isoformat(),
                task.created_by_actor_id,
                task.supersedes_revision,
            ),
        )


def _row_to_task(row: sqlite3.Row) -> TaskRecord:
    return TaskRecord(
        record_id=str(row["record_id"]),
        tenant_id=str(row["tenant_id"]),
        object_id=str(row["object_id"]),
        revision=int(row["revision"]),
        workspace_object_id=str(row["workspace_object_id"]),
        mission_object_id=str(row["mission_object_id"]),
        title=str(row["title"]),
        state=str(row["state"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        created_by_actor_id=str(row["created_by_actor_id"]),
        supersedes_revision=(
            int(row["supersedes_revision"])
            if row["supersedes_revision"] is not None
            else None
        ),
        content_hash=str(row["content_hash"]),
        schema_version=str(row["schema_version"]),
    )
