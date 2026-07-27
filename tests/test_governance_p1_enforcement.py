"""P1 enforcement gaps: contention, authority immutability, migrate copy, run/decision."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime, timedelta

import pytest

from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.grants import DelegatedGrant
from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.commands import CommandEnvelope
from holodeck_governance.domain.errors import MissingAuthorityError, RevisionImmutableError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records.review import ApprovalRecord
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.command_service import CommandService
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
)
from holodeck_governance.storage.sqlite.reconstruction import reconstruct_from_command
from holodeck_governance.storage.sqlite.runs import SqliteRunRepository
from holodeck_governance.storage.sqlite.tasks import SqliteTaskRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FixtureIds
from holodeck_governance.testing.seed import (
    seed_authorized_run_world,
    seed_authorized_task_world,
)


def _task_cmd(world: dict[str, str], **overrides) -> CommandEnvelope:
    base = dict(
        command_id=generate_uuidv7(),
        command_type="task.transition",
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        target_object_id=world["task_object_id"],
        expected_revision=1,
        idempotency_key=generate_uuidv7(),
        payload_schema_version="m1.command.task_transition.v1",
        correlation_id=generate_uuidv7(),
        issued_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        payload={"to_state": "ready"},
    )
    base.update(overrides)
    return CommandEnvelope(**base)


def test_grant_issuance_requires_active_delegation_basis() -> None:
    """M1-034: an authority row cannot create authority by itself."""
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn, permissions=())
    auth = SqliteAuthorityRepository(conn)
    worker_id = generate_uuidv7()
    auth.save_actor(
        Actor(worker_id, world["tenant_id"], ActorKind.AGENT, "Worker", now, world["actor_id"])
    )
    with pytest.raises(MissingAuthorityError):
        auth.save_grant(
            DelegatedGrant(
                grant_id=generate_uuidv7(), tenant_id=world["tenant_id"],
                delegator_actor_id=world["actor_id"], recipient_actor_id=worker_id,
                permission="transition_task", subject_object_id=world["task_object_id"],
                subject_revision=1, effective_from=now, expires_at=now + timedelta(hours=1),
                created_at=now, created_by_actor_id=world["actor_id"],
                issuance_basis_id=world["role_assignment_id"],
            )
        )


def test_competing_task_transitions_yield_structured_stale_receipt(tmp_path) -> None:
    db = tmp_path / "contend.db"
    setup = sqlite3.connect(db)
    setup.row_factory = sqlite3.Row
    world = seed_authorized_task_world(setup)
    setup.close()

    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def worker(key: str) -> None:
        conn = sqlite3.connect(db, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        service = CommandService(conn)
        command = _task_cmd(world, idempotency_key=key, expected_revision=1)
        barrier.wait()
        try:
            results.append(service.handle(command))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            conn.close()

    threads = [
        threading.Thread(target=worker, args=("compete-a",)),
        threading.Thread(target=worker, args=("compete-b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors
    assert len(results) == 2
    outcomes = sorted(r.outcome for r in results)
    assert outcomes == ["accepted", "rejected"]
    loser = next(r for r in results if r.outcome == "rejected")
    assert loser.error_code == DomainErrorCode.STALE_REVISION.value
    assert ReasonCode.DENY_STALE_REVISION.value in loser.reason_codes
    assert loser.evaluation_result_id is not None
    verify = sqlite3.connect(db)
    verify.row_factory = sqlite3.Row
    assert verify.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 1
    assert verify.execute("SELECT COUNT(*) FROM gov_command_receipts").fetchone()[0] == 2
    assert (
        verify.execute("SELECT COUNT(*) FROM gov_evaluation_results").fetchone()[0] == 2
    )
    task = SqliteTaskRepository(verify).get_head_task(world["task_object_id"])
    assert task is not None and task.revision == 2 and task.state == "ready"
    verify.close()


def test_authority_records_reject_in_place_overwrite() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    auth = SqliteAuthorityRepository(conn)
    actor = Actor(
        actor_id=ids.human_owner,
        tenant_id=ids.tenant_alpha,
        kind=ActorKind.HUMAN,
        display_name="Owner",
        created_at=now,
        created_by_actor_id=ids.system_service,
    )
    auth.save_actor(actor)
    with pytest.raises(RevisionImmutableError):
        auth.save_actor(
            Actor(
                actor_id=ids.human_owner,
                tenant_id=ids.tenant_alpha,
                kind=ActorKind.HUMAN,
                display_name="Renamed",
                created_at=now,
                created_by_actor_id=ids.system_service,
            )
        )
    grant = DelegatedGrant(
        grant_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        delegator_actor_id=ids.human_owner,
        recipient_actor_id=ids.human_owner,
        permission="transition_task",
        subject_object_id=ids.mission_object,
        subject_revision=1,
        effective_from=now,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        created_by_actor_id=ids.system_service,
    )
    # Subject object must exist for FK on later tables; grants table refs are soft.
    from holodeck_governance.domain.registry import GovernanceObject
    from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository

    revisions = SqliteRevisionRepository(conn)
    revisions.register_object(
        GovernanceObject(
            object_id=ids.mission_object,
            tenant_id=ids.tenant_alpha,
            object_type="Mission",
            created_at=now,
            created_by_actor_id=ids.system_service,
        )
    )
    # A grant without an issuance basis is intentionally fail-closed.
    from holodeck_governance.domain.errors import MissingAuthorityError

    with pytest.raises(MissingAuthorityError):
        auth.save_grant(grant)
    approval = ApprovalRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=generate_uuidv7(),
        revision=1,
        subject_object_id=ids.mission_object,
        subject_revision=1,
        created_at=now,
        created_by_actor_id=ids.human_owner,
        decision="approved",
    )
    auth.save_approval(approval)
    with pytest.raises(RevisionImmutableError):
        auth.save_approval(approval)
    loaded = auth.get_actor(ids.human_owner)
    assert loaded is not None and loaded.display_name == "Owner"


def test_migrate_v5_preserves_preexisting_command_path_rows(tmp_path) -> None:
    from holodeck_governance.storage.sqlite.migrations import (
        GOVERNANCE_MIGRATIONS,
        migration_now,
    )

    db = tmp_path / "pre_v5.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE gov_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    # Apply numbered migrations through v4 only.
    for version, _name, upgrade in GOVERNANCE_MIGRATIONS:
        if version > 4:
            break
        upgrade(conn)
        conn.execute(
            "INSERT INTO gov_schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, migration_now()),
        )
    tenant = FixtureIds().tenant_alpha
    actor = FixtureIds().system_service
    subject = FixtureIds().mission_object
    stamp = datetime(2026, 7, 24, tzinfo=UTC).isoformat()
    # Do not call ensure_default_local_tenant here: it runs migrate_governance and
    # would apply v5/v6 before the lazy command-path fixture exists.
    conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'alpha', 'Alpha', 'm1.tenant.v1', ?, ?, NULL, 'active', 1)
        """,
        (tenant, stamp, actor),
    )
    conn.execute(
        """
        INSERT INTO gov_objects(
            object_id, tenant_id, object_type, schema_version, created_at,
            created_by_actor_id
        ) VALUES (?, ?, 'Mission', 'm1.governance_object.v1', ?, ?)
        """,
        (subject, tenant, stamp, actor),
    )
    # Lazy pre-v5 command-path tables.
    for table in (
        "gov_outbox_attempts",
        "gov_outbox_items",
        "gov_transition_records",
        "gov_domain_events",
        "gov_evaluation_results",
        "gov_evaluation_snapshots",
        "gov_command_receipts",
    ):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.executescript(
        """
        CREATE TABLE gov_command_receipts(
            receipt_id TEXT PRIMARY KEY,
            command_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            semantic_hash TEXT NOT NULL,
            outcome TEXT NOT NULL,
            reason_codes_json TEXT NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE gov_domain_events(
            event_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            ledger_sequence INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            causation_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE gov_outbox_items(
            outbox_item_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            domain_event_id TEXT NOT NULL,
            delivery_purpose TEXT NOT NULL,
            dedup_key TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE gov_transition_records(
            transition_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            subject_object_id TEXT NOT NULL,
            from_state TEXT NOT NULL,
            to_state TEXT NOT NULL,
            definition_version TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    receipt_id = generate_uuidv7()
    command_id = generate_uuidv7()
    event_id = generate_uuidv7()
    outbox_id = generate_uuidv7()
    transition_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_command_receipts VALUES
        (?, ?, ?, 'lazy-key', 'hash', 'accepted', '["reason.allowed"]', NULL, ?)
        """,
        (receipt_id, command_id, tenant, stamp),
    )
    conn.execute(
        """
        INSERT INTO gov_domain_events VALUES
        (?, ?, 1, 'governance.command.accepted', '{}', ?, ?, ?)
        """,
        (event_id, tenant, generate_uuidv7(), command_id, stamp),
    )
    conn.execute(
        """
        INSERT INTO gov_outbox_items VALUES
        (?, ?, ?, 'command_accepted', ?, 'pending', ?)
        """,
        (outbox_id, tenant, event_id, f"{tenant}:{event_id}:command_accepted", stamp),
    )
    conn.execute(
        """
        INSERT INTO gov_transition_records VALUES
        (?, ?, ?, 'draft', 'ready', 'm1.task_lifecycle.v1', ?)
        """,
        (transition_id, tenant, subject, stamp),
    )
    conn.commit()
    assert governance_schema_version(conn) == 4
    migrate_governance(conn)
    assert governance_schema_version(conn) == 12
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_command_receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_domain_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_outbox_items WHERE outbox_item_id = ?",
            (outbox_id,),
        ).fetchone()[0]
        == 1
    )
    row = conn.execute(
        "SELECT command_id FROM gov_transition_records WHERE transition_id = ?",
        (transition_id,),
    ).fetchone()
    assert row is not None
    assert str(row["command_id"]).startswith("legacy-pre-v5-")
    conn.close()


def test_run_transition_persists_decision_and_reconstructs() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_run_world(conn)
    service = CommandService(conn)
    command = CommandEnvelope(
        command_id=generate_uuidv7(),
        command_type="run.transition",
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        target_object_id=world["run_object_id"],
        expected_revision=1,
        idempotency_key="run-1",
        payload_schema_version="m1.command.run_transition.v1",
        correlation_id=generate_uuidv7(),
        issued_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        payload={"to_state": "active"},
    )
    receipt = service.handle(command)
    assert receipt.outcome == "accepted"
    run = SqliteRunRepository(conn).get_head_run(world["run_object_id"])
    assert run is not None and run.state == "active" and run.revision == 2
    assert conn.execute("SELECT COUNT(*) FROM gov_decisions").fetchone()[0] == 1
    decision = conn.execute(
        "SELECT outcome, command_id FROM gov_decisions WHERE command_id = ?",
        (command.command_id,),
    ).fetchone()
    assert decision is not None
    assert decision["outcome"] == "accepted"
    reconstructed = reconstruct_from_command(
        conn, tenant_id=world["tenant_id"], command_id=command.command_id
    )
    assert reconstructed.receipt["outcome"] == "accepted"
    assert reconstructed.transitions
    assert reconstructed.evaluation_result is not None
    assert reconstructed.decisions
    assert reconstructed.decisions[0]["outcome"] == "accepted"
    # Task accept also writes DecisionRecord
    task_receipt = service.handle(
        _task_cmd(
            world,
            expected_revision=1,
            payload={"to_state": "submitted"},
            idempotency_key="task-dec",
        )
    )
    # task is active from seed; submitted is valid from active
    assert task_receipt.outcome == "accepted"
    assert conn.execute("SELECT COUNT(*) FROM gov_decisions").fetchone()[0] == 2


def test_jurisdiction_mismatch_denies_transition() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    # Point assignment at a different in-tenant workspace jurisdiction.
    other_ws = generate_uuidv7()
    from holodeck_governance.domain.registry import GovernanceObject
    from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository

    SqliteRevisionRepository(conn).register_object(
        GovernanceObject(
            object_id=other_ws,
            tenant_id=world["tenant_id"],
            object_type="Workspace",
            created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
            created_by_actor_id=world["actor_id"],
        )
    )
    conn.execute(
        """
        UPDATE gov_role_assignments
        SET jurisdiction_value = ?, workspace_object_id = ?
        """,
        (other_ws, other_ws),
    )
    conn.commit()
    receipt = CommandService(conn).handle(_task_cmd(world, idempotency_key="juris-deny"))
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_MISSING_AUTHORITY.value in receipt.reason_codes


def test_expired_grant_preserves_grant_expired_reason() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn, permissions=("delegate:transition_task",))
    auth = SqliteAuthorityRepository(conn)
    auth.save_actor(
        Actor(
            actor_id=ids.worker_agent,
            tenant_id=world["tenant_id"],
            kind=ActorKind.AGENT,
            display_name="Worker",
            created_at=now,
                created_by_actor_id=world["actor_id"],
        )
    )
    auth.save_grant(
        DelegatedGrant(
            grant_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            delegator_actor_id=world["actor_id"],
            recipient_actor_id=ids.worker_agent,
            permission="transition_task",
            subject_object_id=world["task_object_id"],
            subject_revision=1,
            effective_from=now - timedelta(hours=2),
            expires_at=now - timedelta(minutes=1),
            created_at=now,
            created_by_actor_id=world["actor_id"],
            issuance_basis_id=world["role_assignment_id"],
        )
    )
    conn.commit()
    denied = CommandService(conn).handle(
        _task_cmd(
            world,
            actor_id=ids.worker_agent,
            idempotency_key="grant-expired-strict",
            issued_at=now,
        )
    )
    assert denied.outcome == "rejected"
    assert ReasonCode.DENY_GRANT_EXPIRED.value in denied.reason_codes


def test_run_transition_requires_transition_run_permission() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Task-only permission must not authorize run.transition.
    world = seed_authorized_task_world(conn, permissions=("transition_task",))
    from holodeck_governance.domain.records.run import RunRecord

    run_object_id = generate_uuidv7()
    SqliteRunRepository(conn).create_run(
        RunRecord(
            record_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            object_id=run_object_id,
            revision=1,
            task_object_id=world["task_object_id"],
            mission_object_id=world["mission_object_id"],
            state="created",
            created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
            created_by_actor_id=world["actor_id"],
        )
    )
    conn.commit()
    receipt = CommandService(conn).handle(
        CommandEnvelope(
            command_id=generate_uuidv7(),
            command_type="run.transition",
            tenant_id=world["tenant_id"],
            actor_id=world["actor_id"],
            target_object_id=run_object_id,
            expected_revision=1,
            idempotency_key="run-no-perm",
            payload_schema_version="m1.command.run_transition.v1",
            correlation_id=generate_uuidv7(),
            issued_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
            payload={"to_state": "active"},
        )
    )
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_MISSING_AUTHORITY.value in receipt.reason_codes


def test_migrate_v5_edge_copy_failure_preserves_table() -> None:
    from holodeck_governance.storage.sqlite.migrations import (
        GOVERNANCE_MIGRATIONS,
        migration_now,
    )

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gov_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    # Apply only through v4.
    for version, _name, upgrade in GOVERNANCE_MIGRATIONS:
        if version > 4:
            break
        upgrade(conn)
        conn.execute(
            "INSERT INTO gov_schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, migration_now()),
        )
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC).isoformat()
    conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'alpha', 'Alpha', 'm1.tenant.v1', ?, ?, NULL, 'active', 1)
        """,
        (ids.tenant_alpha, now, ids.system_service),
    )
    # Orphaned edge: no matching gov_object_revisions, so v5 FK copy must fail.
    edge_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_traceability_edges(
            edge_id, tenant_id, edge_type, from_object_id, from_revision,
            to_object_id, to_revision, created_at, created_by_actor_id,
            provenance_ref, validity_status, schema_version
        ) VALUES (?, ?, 'supports', ?, 1, ?, 1, ?, ?, NULL, 'valid', 'm1.edge.v1')
        """,
        (
            edge_id,
            ids.tenant_alpha,
            generate_uuidv7(),
            generate_uuidv7(),
            now,
            ids.system_service,
        ),
    )
    conn.commit()
    with pytest.raises(Exception):
        migrate_governance(conn)
    assert governance_schema_version(conn) == 4
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_traceability_edges WHERE edge_id = ?",
            (edge_id,),
        ).fetchone()[0]
        == 1
    )


def test_outbox_record_attempt_requires_lease_owner() -> None:
    from holodeck_governance.storage.sqlite.outbox import OutboxWorker

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    CommandService(conn).handle(_task_cmd(world, idempotency_key="outbox-fence"))
    worker = OutboxWorker(conn, max_attempts=3)
    now = datetime(2026, 7, 24, 12, 1, tzinfo=UTC)
    item = worker.claim(worker_id="owner-a", now=now)
    assert item is not None
    with pytest.raises(PermissionError):
        worker.record_attempt(
            item,
            success=True,
            now=now,
            subject_object_id=world["task_object_id"],
            tenant_id=world["tenant_id"],
            actor_id=world["actor_id"],
            lease_owner="owner-b",
        )
    status = conn.execute(
        "SELECT status, lease_owner FROM gov_outbox_items WHERE outbox_item_id = ?",
        (item,),
    ).fetchone()
    assert status["status"] == "leased"
    assert status["lease_owner"] == "owner-a"


def test_adapter_rejects_nested_forbidden_authority_fields(tmp_path) -> None:
    from holodeck_control_plane.errors import ValidationError
    from holodeck_control_plane.governance_commands import (
        submit_governance_command_request,
    )

    db = tmp_path / "nested.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    conn.close()
    with pytest.raises(ValidationError) as raised:
        submit_governance_command_request(
            str(db),
            {
                "command": {
                    "command_id": generate_uuidv7(),
                    "command_type": "task.transition",
                    "tenant_id": world["tenant_id"],
                    "actor_id": world["actor_id"],
                    "target_object_id": world["task_object_id"],
                    "expected_revision": 1,
                    "idempotency_key": "nested-forbid",
                    "payload_schema_version": "m1.command.task_transition.v1",
                    "correlation_id": generate_uuidv7(),
                    "issued_at": datetime(2026, 7, 24, 12, 0, tzinfo=UTC).isoformat(),
                    "payload": {
                        "to_state": "ready",
                        "actor_permitted": True,
                    },
                },
            },
        )
    assert "command.payload.actor_permitted" in str(raised.value)


def test_role_profile_persists_jurisdiction_json() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    row = conn.execute(
        """
        SELECT jurisdiction_json FROM gov_role_profiles
        WHERE role_object_id = ?
        """,
        (world["role_object_id"],),
    ).fetchone()
    assert row is not None
    payload = __import__("json").loads(row["jurisdiction_json"])
    assert payload["workspace"] == world["workspace_object_id"]
