"""Persisted run records and governed state transitions."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from holodeck_governance.domain.errors import NotFoundGovernanceError, StaleRevisionError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records.run import RunRecord
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.revisions import ObjectRevision, content_hash_for
from holodeck_governance.domain.tenant import assert_same_tenant
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository


class SqliteRunRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        migrate_governance(conn)
        self._revisions = SqliteRevisionRepository(conn)

    def create_run(self, run: RunRecord) -> RunRecord:
        payload = {
            "state": run.state,
            "task_object_id": run.task_object_id,
            "mission_object_id": run.mission_object_id,
        }
        digest = run.content_hash or content_hash_for(payload)
        if self._revisions.get_object(run.object_id) is None:
            self._revisions.register_object(
                GovernanceObject(
                    object_id=run.object_id,
                    tenant_id=run.tenant_id,
                    object_type="Run",
                    created_at=run.created_at,
                    created_by_actor_id=run.created_by_actor_id,
                )
            )
        self._insert_run_row(run, digest)
        if self._revisions.get_revision(run.object_id, run.revision) is None:
            revision = ObjectRevision(
                revision_id=generate_uuidv7(),
                tenant_id=run.tenant_id,
                object_id=run.object_id,
                revision=run.revision,
                content_hash=digest,
                payload=payload,
                created_at=run.created_at,
                created_by_actor_id=run.created_by_actor_id,
                supersedes_revision=None,
                finalized=True,
            )
            self._revisions._insert_revision(revision)
            self._revisions._upsert_head(revision)
        return run

    def get_head_run(self, object_id: str) -> RunRecord | None:
        head = self._revisions.get_head(object_id)
        if head is None:
            return None
        return self.get_run(object_id, head.head_revision)

    def get_run(self, object_id: str, revision: int) -> RunRecord | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_runs
            WHERE object_id = ? AND revision = ?
            """,
            (object_id, revision),
        ).fetchone()
        return _row_to_run(row) if row else None

    def require_tenant_run(self, *, object_id: str, tenant_id: str) -> RunRecord:
        obj = self._revisions.get_object(object_id)
        if obj is None:
            raise NotFoundGovernanceError(f"unknown object {object_id}")
        if obj.object_type != "Run":
            raise NotFoundGovernanceError(f"object {object_id} is not a Run")
        assert_same_tenant(
            actor_tenant_id=tenant_id,
            record_tenant_id=obj.tenant_id,
            context="run",
        )
        run = self.get_head_run(object_id)
        if run is None:
            raise NotFoundGovernanceError(f"run {object_id} has no head record")
        return run

    def apply_transition(
        self,
        *,
        current: RunRecord,
        to_state: str,
        actor_id: str,
        created_at: datetime,
        expected_revision: int | None,
    ) -> RunRecord:
        head = self.get_head_run(current.object_id)
        if head is None:
            raise StaleRevisionError(f"run {current.object_id} has no head")
        if expected_revision is not None and head.revision != expected_revision:
            raise StaleRevisionError(
                f"expected revision {expected_revision}, head is {head.revision}"
            )
        if head.revision != current.revision:
            raise StaleRevisionError(
                f"stale run view {current.revision}, head is {head.revision}"
            )
        next_revision = head.revision + 1
        payload = {
            "state": to_state,
            "task_object_id": head.task_object_id,
            "mission_object_id": head.mission_object_id,
        }
        digest = content_hash_for(payload)
        new_run = RunRecord(
            record_id=generate_uuidv7(),
            tenant_id=head.tenant_id,
            object_id=head.object_id,
            revision=next_revision,
            task_object_id=head.task_object_id,
            mission_object_id=head.mission_object_id,
            state=to_state,
            created_at=created_at,
            created_by_actor_id=actor_id,
            content_hash=digest,
        )
        try:
            self._insert_run_row(new_run, digest)
            revision = ObjectRevision(
                revision_id=generate_uuidv7(),
                tenant_id=new_run.tenant_id,
                object_id=new_run.object_id,
                revision=new_run.revision,
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
                f"concurrent run transition lost for {current.object_id}"
            ) from exc
        return new_run

    def _insert_run_row(self, run: RunRecord, digest: str) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_runs(
                record_id, tenant_id, object_id, revision, task_object_id,
                mission_object_id, state, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.record_id,
                run.tenant_id,
                run.object_id,
                run.revision,
                run.task_object_id,
                run.mission_object_id,
                run.state,
                digest,
                run.schema_version,
                run.created_at.isoformat(),
                run.created_by_actor_id,
            ),
        )


def _row_to_run(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        record_id=str(row["record_id"]),
        tenant_id=str(row["tenant_id"]),
        object_id=str(row["object_id"]),
        revision=int(row["revision"]),
        task_object_id=str(row["task_object_id"]),
        mission_object_id=str(row["mission_object_id"]),
        state=str(row["state"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        created_by_actor_id=str(row["created_by_actor_id"]),
        content_hash=str(row["content_hash"]),
        schema_version=str(row["schema_version"]),
    )
