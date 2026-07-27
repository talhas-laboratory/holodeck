"""Command path tests for enforced persistence and authorization."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.commands import CommandEnvelope
from holodeck_governance.domain.errors import IdempotencyConflictError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.storage.sqlite.command_service import CommandService
from holodeck_governance.storage.sqlite.tasks import SqliteTaskRepository
from holodeck_governance.testing import FixtureIds
from holodeck_governance.testing.seed import seed_authorized_task_world


def _service() -> tuple[CommandService, dict[str, str]]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    return CommandService(conn), world


def _command(world: dict[str, str], **overrides):
    base = dict(
        command_id=generate_uuidv7(),
        command_type="task.transition",
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        target_object_id=world["task_object_id"],
        expected_revision=1,
        idempotency_key="key-1",
        payload_schema_version="m1.command.task_transition.v1",
        correlation_id=generate_uuidv7(),
        issued_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        payload={"to_state": "ready"},
    )
    base.update(overrides)
    return CommandEnvelope(**base)


def test_rejected_invalid_transition_has_receipt_without_success_effects_gs011() -> None:
    service, world = _service()
    receipt = service.handle(_command(world, payload={"to_state": "accepted"}))
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_INVALID_TRANSITION.value in receipt.reason_codes
    assert receipt.error_code == DomainErrorCode.INVALID_TRANSITION.value
    conn = service._conn
    assert conn.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_command_receipts").fetchone()[0] == 1
    task = SqliteTaskRepository(conn).get_head_task(world["task_object_id"])
    assert task is not None and task.state == "draft"


def test_accepted_transition_mutates_task_and_writes_effects() -> None:
    service, world = _service()
    receipt = service.handle(_command(world))
    assert receipt.outcome == "accepted"
    conn = service._conn
    task = SqliteTaskRepository(conn).get_head_task(world["task_object_id"])
    assert task is not None
    assert task.state == "ready"
    assert task.revision == 2
    assert conn.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_domain_events").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_evaluation_results").fetchone()[0] == 1


def test_random_target_is_rejected_not_accepted() -> None:
    service, world = _service()
    receipt = service.handle(
        _command(world, target_object_id=generate_uuidv7(), idempotency_key="rand")
    )
    assert receipt.outcome == "rejected"
    assert receipt.error_code == DomainErrorCode.NOT_FOUND.value


def test_idempotent_retry_and_conflict_gs007() -> None:
    service, world = _service()
    first = service.handle(_command(world))
    second = service.handle(
        _command(world, command_id=generate_uuidv7(), idempotency_key="key-1")
    )
    assert first.receipt_id == second.receipt_id
    assert service._conn.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 1
    with pytest.raises(IdempotencyConflictError):
        service.handle(
            _command(
                world,
                command_id=generate_uuidv7(),
                idempotency_key="key-1",
                payload={"to_state": "blocked"},
            )
        )


def test_cross_tenant_command_rejected_without_event_gs001() -> None:
    service, world = _service()
    beta = FixtureIds().tenant_beta
    service._conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'beta', 'Beta', 'm1.tenant.v1', ?, ?, NULL, 'active', 0)
        """,
        (
            beta,
            datetime(2026, 7, 24, 12, 0, tzinfo=UTC).isoformat(),
            FixtureIds().system_service,
        ),
    )
    service._conn.commit()
    receipt = service.handle(
        _command(
            world,
            tenant_id=beta,
            idempotency_key="xt",
        )
    )
    assert receipt.outcome == "rejected"
    assert receipt.error_code == DomainErrorCode.CROSS_TENANT_ACCESS.value
    assert ReasonCode.DENY_TENANT_ISOLATION.value in receipt.reason_codes
    conn = service._conn
    assert conn.execute("SELECT COUNT(*) FROM gov_domain_events").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_command_receipts").fetchone()[0] == 1


def test_missing_authority_is_resolved_from_records() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn, permissions=())
    service = CommandService(conn)
    receipt = service.handle(_command(world, idempotency_key="noauth"))
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_MISSING_AUTHORITY.value in receipt.reason_codes


def test_stale_revision_from_persisted_head() -> None:
    service, world = _service()
    receipt = service.handle(
        _command(world, expected_revision=9, idempotency_key="stale")
    )
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_STALE_REVISION.value in receipt.reason_codes


def test_fault_injection_rolls_back_success_set_gs010() -> None:
    service, world = _service()
    service._fault_before = "after:evaluation"
    with pytest.raises(RuntimeError, match="injected fault after evaluation"):
        service.handle(_command(world, idempotency_key="fault-1"))
    conn = service._conn
    assert conn.execute("SELECT COUNT(*) FROM gov_command_receipts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_evaluation_results").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 0
    task = SqliteTaskRepository(conn).get_head_task(world["task_object_id"])
    assert task is not None and task.state == "draft" and task.revision == 1


def test_policy_binding_required_approvals_enforced_from_storage() -> None:
    from holodeck_governance.domain.policy.binding import PolicyBinding
    from holodeck_governance.storage.sqlite.policy import SqlitePolicyRepository

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    SqlitePolicyRepository(conn).save(
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            scope="tenant",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "1"},
            created_at=now,
            created_by_actor_id=world["actor_id"],
            precedence=10,
            effective_from=now,
        )
    )
    conn.commit()
    service = CommandService(conn)
    receipt = service.handle(_command(world, idempotency_key="needs-approval"))
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_STALE_APPROVAL.value in receipt.reason_codes
    assert conn.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 0


def test_concurrent_idempotent_writes_share_one_receipt(tmp_path) -> None:
    import threading

    db = tmp_path / "idem.db"
    setup = sqlite3.connect(db)
    setup.row_factory = sqlite3.Row
    world = seed_authorized_task_world(setup)
    setup.close()

    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def worker() -> None:
        conn = sqlite3.connect(db, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        service = CommandService(conn)
        command = _command(
            world,
            command_id=generate_uuidv7(),
            idempotency_key="concurrent-key",
        )
        barrier.wait()
        try:
            results.append(service.handle(command))
        except Exception as exc:  # noqa: BLE001 - collect for assertion
            errors.append(exc)
        finally:
            conn.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(results) == 2
    assert results[0].receipt_id == results[1].receipt_id
    assert results[0].outcome == "accepted"
    verify = sqlite3.connect(db)
    verify.row_factory = sqlite3.Row
    assert verify.execute("SELECT COUNT(*) FROM gov_command_receipts").fetchone()[0] == 1
    assert verify.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 1
    task = SqliteTaskRepository(verify).get_head_task(world["task_object_id"])
    assert task is not None and task.state == "ready" and task.revision == 2
    verify.close()
