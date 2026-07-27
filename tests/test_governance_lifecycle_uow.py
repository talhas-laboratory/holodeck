"""Lifecycle and unit-of-work tests (M1-013, M1-030)."""

from __future__ import annotations

import sqlite3

import pytest

from holodeck_governance.domain.errors import InvalidTransitionError
from holodeck_governance.domain.lifecycle import (
    TASK_DEFINITION_VERSION,
    validate_run_transition,
    validate_task_transition,
)
from holodeck_governance.storage.sqlite.uow import SqliteUnitOfWork


def test_task_and_run_transitions_versioned_gs006() -> None:
    assert validate_task_transition("draft", "ready") == TASK_DEFINITION_VERSION
    assert validate_run_transition("created", "active")
    with pytest.raises(InvalidTransitionError):
        validate_task_transition("accepted", "ready")
    with pytest.raises(InvalidTransitionError):
        validate_run_transition("completed", "active")


def test_unit_of_work_all_or_nothing_fault_injection() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE marker(name TEXT PRIMARY KEY)")

    def write(name: str):
        def _writer(c: sqlite3.Connection) -> None:
            c.execute("INSERT INTO marker(name) VALUES (?)", (name,))

        return _writer

    uow = SqliteUnitOfWork(conn, fault_before="after:evaluation")
    for step in ("receipt", "evaluation", "transition", "event", "outbox"):
        uow.add(step, write(step))
    with pytest.raises(RuntimeError, match="injected fault after evaluation"):
        uow.commit()
    assert conn.execute("SELECT COUNT(*) FROM marker").fetchone()[0] == 0

    uow2 = SqliteUnitOfWork(conn)
    for step in ("receipt", "evaluation", "transition", "event", "outbox"):
        uow2.add(step, write(f"ok-{step}"))
    uow2.commit()
    assert conn.execute("SELECT COUNT(*) FROM marker").fetchone()[0] == 5


def test_typed_repositories_persist_through_command_service() -> None:
    from holodeck_governance.domain.commands import CommandEnvelope
    from holodeck_governance.domain.ids import generate_uuidv7
    from holodeck_governance.storage.sqlite.command_service import CommandService
    from holodeck_governance.storage.sqlite.repos import (
        SqliteCommandReceiptRepository,
        SqliteEvaluationRepository,
    )
    from holodeck_governance.storage.sqlite.tenants import SqliteTenantRepository
    from holodeck_governance.testing.seed import seed_authorized_task_world
    from datetime import UTC, datetime

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    assert SqliteTenantRepository(conn).get(world["tenant_id"]) is not None
    service = CommandService(conn)
    command = CommandEnvelope(
        command_id=generate_uuidv7(),
        command_type="task.transition",
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        target_object_id=world["task_object_id"],
        expected_revision=1,
        idempotency_key="repo-1",
        payload_schema_version="m1.command.task_transition.v1",
        correlation_id=generate_uuidv7(),
        issued_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        payload={"to_state": "ready"},
    )
    receipt = service.handle(command)
    loaded = SqliteCommandReceiptRepository(conn).get_by_idempotency(
        world["tenant_id"], "repo-1"
    )
    assert loaded is not None
    assert loaded[1].receipt_id == receipt.receipt_id
    assert conn.execute("SELECT COUNT(*) FROM gov_evaluation_results").fetchone()[0] == 1
    assert isinstance(SqliteEvaluationRepository(conn), SqliteEvaluationRepository)
