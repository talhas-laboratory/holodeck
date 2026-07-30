"""SQLite persistence for governance objects, revisions, and heads."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Mapping

from holodeck_governance.domain.errors import RevisionImmutableError, StaleRevisionError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.revisions import (
    ObjectHead,
    ObjectRevision,
    content_hash_for,
)
from holodeck_governance.domain.tenant import assert_same_tenant
from holodeck_governance.storage.sqlite.migrations import migrate_governance


class SqliteRevisionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def register_object(self, obj: GovernanceObject) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_objects(
                object_id, tenant_id, object_type, schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                obj.object_id,
                obj.tenant_id,
                obj.object_type,
                obj.schema_version,
                obj.created_at.isoformat(),
                obj.created_by_actor_id,
            ),
        )

    def get_object(self, object_id: str) -> GovernanceObject | None:
        row = self._conn.execute(
            "SELECT * FROM gov_objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            return None
        return GovernanceObject(
            object_id=str(row["object_id"]),
            tenant_id=str(row["tenant_id"]),
            object_type=str(row["object_type"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            schema_version=str(row["schema_version"]),
        )

    def get_revision(self, object_id: str, revision: int) -> ObjectRevision | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_object_revisions
            WHERE object_id = ? AND revision = ?
            """,
            (object_id, revision),
        ).fetchone()
        return _row_to_revision(row) if row else None

    def get_head(self, object_id: str) -> ObjectHead | None:
        row = self._conn.execute(
            "SELECT * FROM gov_object_heads WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            return None
        return ObjectHead(
            object_id=str(row["object_id"]),
            tenant_id=str(row["tenant_id"]),
            head_revision=int(row["head_revision"]),
            head_revision_id=str(row["head_revision_id"]),
        )

    def create_initial_revision(
        self,
        *,
        obj: GovernanceObject,
        payload: Mapping[str, Any],
        revision_id: str | None = None,
    ) -> ObjectRevision:
        migrate_governance(self._conn)
        self.register_object(obj)
        revision = ObjectRevision(
            revision_id=revision_id or generate_uuidv7(),
            tenant_id=obj.tenant_id,
            object_id=obj.object_id,
            revision=1,
            content_hash=content_hash_for(payload),
            payload=dict(payload),
            created_at=obj.created_at,
            created_by_actor_id=obj.created_by_actor_id,
            supersedes_revision=None,
            finalized=True,
        )
        self._insert_revision(revision)
        self._upsert_head(revision)
        return revision

    def append_correction(
        self,
        *,
        object_id: str,
        tenant_id: str,
        actor_id: str,
        created_at: datetime,
        payload: Mapping[str, Any],
        expected_head_revision: int,
        revision_id: str | None = None,
    ) -> ObjectRevision:
        """Create a linked correction revision and advance head atomically."""

        obj = self.get_object(object_id)
        if obj is None:
            raise StaleRevisionError(f"unknown object {object_id}")
        assert_same_tenant(
            actor_tenant_id=tenant_id,
            record_tenant_id=obj.tenant_id,
            context="append_correction",
        )
        head = self.get_head(object_id)
        if head is None:
            raise StaleRevisionError(f"object {object_id} has no head")
        if head.head_revision != expected_head_revision:
            raise StaleRevisionError(
                f"expected head {expected_head_revision}, found {head.head_revision}"
            )
        current = self.get_revision(object_id, head.head_revision)
        if current is None:
            raise StaleRevisionError("head revision missing")
        # Prior finalized revision remains immutable; correction inserts a new row.

        next_revision = head.head_revision + 1
        revision = ObjectRevision(
            revision_id=revision_id or generate_uuidv7(),
            tenant_id=obj.tenant_id,
            object_id=object_id,
            revision=next_revision,
            content_hash=content_hash_for(payload),
            payload=dict(payload),
            created_at=created_at,
            created_by_actor_id=actor_id,
            supersedes_revision=head.head_revision,
            finalized=True,
        )
        self._insert_revision(revision)
        self._upsert_head(revision)
        return revision

    def reject_in_place_mutation(self, object_id: str, revision: int) -> None:
        existing = self.get_revision(object_id, revision)
        if existing is None:
            raise StaleRevisionError(f"missing revision {object_id}@{revision}")
        raise RevisionImmutableError(
            f"direct mutation of {object_id}@{revision} is forbidden"
        )

    def _insert_revision(self, revision: ObjectRevision) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_object_revisions(
                revision_id, tenant_id, object_id, revision, supersedes_revision,
                content_hash, payload_json, finalized, schema_version, created_at,
                created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision.revision_id,
                revision.tenant_id,
                revision.object_id,
                revision.revision,
                revision.supersedes_revision,
                revision.content_hash,
                json.dumps(dict(revision.payload), sort_keys=True),
                1 if revision.finalized else 0,
                revision.schema_version,
                revision.created_at.isoformat(),
                revision.created_by_actor_id,
            ),
        )

    def _upsert_head(self, revision: ObjectRevision) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_object_heads(object_id, tenant_id, head_revision, head_revision_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(object_id) DO UPDATE SET
                head_revision=excluded.head_revision,
                head_revision_id=excluded.head_revision_id
            """,
            (
                revision.object_id,
                revision.tenant_id,
                revision.revision,
                revision.revision_id,
            ),
        )


def _row_to_revision(row: sqlite3.Row) -> ObjectRevision:
    return ObjectRevision(
        revision_id=str(row["revision_id"]),
        tenant_id=str(row["tenant_id"]),
        object_id=str(row["object_id"]),
        revision=int(row["revision"]),
        content_hash=str(row["content_hash"]),
        payload=json.loads(str(row["payload_json"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        created_by_actor_id=str(row["created_by_actor_id"]),
        supersedes_revision=(
            int(row["supersedes_revision"])
            if row["supersedes_revision"] is not None
            else None
        ),
        finalized=bool(row["finalized"]),
        schema_version=str(row["schema_version"]),
    )
