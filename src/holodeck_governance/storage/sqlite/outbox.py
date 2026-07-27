"""Atomic outbox leasing, retry with backoff, and persisted dead-letter escalation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records.escalation import EscalationRecord
from holodeck_governance.storage.sqlite.migrations import migrate_governance


@dataclass
class OutboxWorker:
    conn: sqlite3.Connection
    max_attempts: int = 3
    lease_seconds: int = 30
    base_backoff_seconds: int = 2

    def ensure_schema(self) -> None:
        migrate_governance(self.conn)

    def claim(self, *, worker_id: str, now: datetime) -> str | None:
        self.ensure_schema()
        until = (now + timedelta(seconds=self.lease_seconds)).isoformat()
        previous = self.conn.isolation_level
        self.conn.isolation_level = None
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute(
                """
                SELECT outbox_item_id FROM gov_outbox_items
                WHERE status IN ('pending', 'leased')
                  AND (lease_until IS NULL OR lease_until <= ?)
                  AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                ORDER BY created_at
                LIMIT 1
                """,
                (now.isoformat(), now.isoformat()),
            ).fetchone()
            if row is None:
                self.conn.execute("COMMIT")
                return None
            item_id = str(row[0])
            updated = self.conn.execute(
                """
                UPDATE gov_outbox_items
                SET lease_owner = ?, lease_until = ?, status = 'leased'
                WHERE outbox_item_id = ?
                  AND (lease_until IS NULL OR lease_until <= ?)
                  AND status IN ('pending', 'leased')
                """,
                (worker_id, until, item_id, now.isoformat()),
            )
            if updated.rowcount != 1:
                self.conn.execute("ROLLBACK")
                return None
            self.conn.execute("COMMIT")
            return item_id
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        finally:
            self.conn.isolation_level = previous

    def record_attempt(
        self,
        item_id: str,
        *,
        success: bool,
        now: datetime,
        subject_object_id: str,
        tenant_id: str,
        actor_id: str,
        lease_owner: str,
    ) -> EscalationRecord | None:
        self.ensure_schema()
        row = self.conn.execute(
            """
            SELECT attempt_count, lease_owner, lease_until, status
            FROM gov_outbox_items WHERE outbox_item_id = ?
            """,
            (item_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"outbox item {item_id} not found")
        owner = row["lease_owner"] if isinstance(row, sqlite3.Row) else row[1]
        until = row["lease_until"] if isinstance(row, sqlite3.Row) else row[2]
        status = row["status"] if isinstance(row, sqlite3.Row) else row[3]
        if owner != lease_owner:
            raise PermissionError(
                f"outbox lease fencing: owner {owner!r} != caller {lease_owner!r}"
            )
        if status != "leased":
            raise PermissionError(f"outbox item {item_id} is not leased")
        if until is not None and str(until) < now.isoformat():
            raise PermissionError(f"outbox lease expired for {item_id}")
        attempt_number = int(
            (row["attempt_count"] if isinstance(row, sqlite3.Row) else row[0]) or 0
        ) + 1
        self.conn.execute(
            """
            INSERT INTO gov_outbox_attempts(attempt_id, outbox_item_id, attempt_number, result, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                generate_uuidv7(),
                item_id,
                attempt_number,
                "success" if success else "failure",
                now.isoformat(),
            ),
        )
        if success:
            updated = self.conn.execute(
                """
                UPDATE gov_outbox_items
                SET status = 'delivered', attempt_count = ?, lease_owner = NULL,
                    lease_until = NULL, next_attempt_at = NULL
                WHERE outbox_item_id = ? AND lease_owner = ? AND status = 'leased'
                """,
                (attempt_number, item_id, lease_owner),
            )
            if updated.rowcount != 1:
                self.conn.rollback()
                raise PermissionError("outbox lease fencing lost on success update")
            self.conn.commit()
            return None
        if attempt_number >= self.max_attempts:
            escalation = EscalationRecord(
                record_id=generate_uuidv7(),
                tenant_id=tenant_id,
                object_id=generate_uuidv7(),
                revision=1,
                subject_object_id=subject_object_id,
                trigger="outbox_dead_letter",
                created_at=now,
                created_by_actor_id=actor_id,
                content_hash="sha256:escalation",
            )
            # Persist escalation as a durable record.
            from holodeck_governance.domain.registry import GovernanceObject
            from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository

            revisions = SqliteRevisionRepository(self.conn)
            revisions.register_object(
                GovernanceObject(
                    object_id=escalation.object_id,
                    tenant_id=tenant_id,
                    object_type="Escalation",
                    created_at=now,
                    created_by_actor_id=actor_id,
                )
            )
            self.conn.execute(
                """
                INSERT INTO gov_escalations(
                    record_id, tenant_id, object_id, revision, subject_object_id,
                    trigger, outbox_item_id, content_hash, schema_version,
                    created_at, created_by_actor_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    escalation.record_id,
                    escalation.tenant_id,
                    escalation.object_id,
                    escalation.revision,
                    escalation.subject_object_id,
                    escalation.trigger,
                    item_id,
                    escalation.content_hash,
                    escalation.schema_version,
                    now.isoformat(),
                    actor_id,
                ),
            )
            updated = self.conn.execute(
                """
                UPDATE gov_outbox_items
                SET status = 'dead_letter', attempt_count = ?, lease_owner = NULL,
                    lease_until = NULL, next_attempt_at = NULL
                WHERE outbox_item_id = ? AND lease_owner = ? AND status = 'leased'
                """,
                (attempt_number, item_id, lease_owner),
            )
            if updated.rowcount != 1:
                self.conn.rollback()
                raise PermissionError("outbox lease fencing lost on dead-letter update")
            self.conn.commit()
            return escalation
        backoff = self.base_backoff_seconds * (2 ** (attempt_number - 1))
        next_at = (now + timedelta(seconds=backoff)).isoformat()
        updated = self.conn.execute(
            """
            UPDATE gov_outbox_items
            SET status = 'pending', attempt_count = ?, lease_owner = NULL,
                lease_until = NULL, next_attempt_at = ?
            WHERE outbox_item_id = ? AND lease_owner = ? AND status = 'leased'
            """,
            (attempt_number, next_at, item_id, lease_owner),
        )
        if updated.rowcount != 1:
            self.conn.rollback()
            raise PermissionError("outbox lease fencing lost on retry update")
        self.conn.commit()
        return None
