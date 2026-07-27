"""Outbox recovery tests (M1-021 / GS-012)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from holodeck_governance.domain.commands import CommandEnvelope
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.storage.sqlite.command_service import CommandService
from holodeck_governance.storage.sqlite.outbox import OutboxWorker
from holodeck_governance.testing.seed import seed_authorized_task_world


def test_outbox_lease_retry_and_dead_letter_gs012() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    service = CommandService(conn)
    service.handle(
        CommandEnvelope(
            command_id=generate_uuidv7(),
            command_type="task.transition",
            tenant_id=world["tenant_id"],
            actor_id=world["actor_id"],
            target_object_id=world["task_object_id"],
            expected_revision=1,
            idempotency_key="outbox-1",
            payload_schema_version="m1.command.task_transition.v1",
            correlation_id=generate_uuidv7(),
            issued_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
            payload={"to_state": "ready"},
        )
    )
    worker = OutboxWorker(conn, max_attempts=2)
    now = datetime(2026, 7, 24, 12, 1, tzinfo=UTC)
    item = worker.claim(worker_id="w1", now=now)
    assert item is not None
    later = datetime(2026, 7, 24, 12, 2, tzinfo=UTC)
    conn.execute(
        "UPDATE gov_outbox_items SET lease_until = ? WHERE outbox_item_id = ?",
        (now.isoformat(), item),
    )
    conn.commit()
    recovered = worker.claim(worker_id="w2", now=later)
    assert recovered == item
    assert (
        worker.record_attempt(
            item,
            success=False,
            now=later,
            subject_object_id=world["task_object_id"],
            tenant_id=world["tenant_id"],
            actor_id=world["actor_id"],
            lease_owner="w2",
        )
        is None
    )
    # Backoff schedules next_attempt_at in the future; force it due and re-claim.
    conn.execute(
        "UPDATE gov_outbox_items SET next_attempt_at = ? WHERE outbox_item_id = ?",
        (later.isoformat(), item),
    )
    conn.commit()
    reclaimed = worker.claim(worker_id="w2", now=later)
    assert reclaimed == item
    dead = worker.record_attempt(
        item,
        success=False,
        now=later,
        subject_object_id=world["task_object_id"],
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        lease_owner="w2",
    )
    assert dead is not None
    assert dead.trigger == "outbox_dead_letter"
    status = conn.execute(
        "SELECT status FROM gov_outbox_items WHERE outbox_item_id = ?", (item,)
    ).fetchone()[0]
    assert status == "dead_letter"
    assert conn.execute("SELECT COUNT(*) FROM gov_escalations").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 1
