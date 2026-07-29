"""Reconstruction and legacy migration support tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from holodeck_control_plane.store import Store
from holodeck_governance.domain.commands import CommandEnvelope
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.legacy_mapping import dry_run_mapping
from holodeck_governance.storage.legacy_seam import (
    LEGACY_COORDINATION_TABLES,
    PROVENANCE_KIND,
)
from holodeck_governance.storage.sqlite.command_service import CommandService
from holodeck_governance.storage.sqlite.legacy_import import (
    import_legacy_database,
    import_legacy_tasks,
)
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
    rollback_governance_migration,
)
from holodeck_governance.storage.sqlite.reconstruction import (
    receipt_reason_codes,
    reconstruct_from_command,
)
from holodeck_governance.testing import FixtureIds


def test_reconstruct_permitted_decision_with_graph_gs013() -> None:
    from holodeck_governance.testing.seed import seed_authorized_task_world

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    service = CommandService(conn)
    command_id = generate_uuidv7()
    service.handle(
        CommandEnvelope(
            command_id=command_id,
            command_type="task.transition",
            tenant_id=world["tenant_id"],
            actor_id=world["actor_id"],
            target_object_id=world["task_object_id"],
            expected_revision=1,
            idempotency_key="recon-1",
            payload_schema_version="m1.command.task_transition.v1",
            correlation_id=generate_uuidv7(),
            issued_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
            payload={"to_state": "ready"},
        )
    )
    reconstructed = reconstruct_from_command(
        conn, tenant_id=world["tenant_id"], command_id=command_id
    )
    assert reconstructed.receipt["outcome"] == "accepted"
    assert receipt_reason_codes(reconstructed.receipt)
    assert reconstructed.evaluation_result is not None
    assert reconstructed.evaluation_snapshot is not None
    assert reconstructed.events
    assert reconstructed.transitions
    assert reconstructed.outbox_items
    assert reconstructed.decisions
    assert reconstructed.decisions[0]["command_id"] == command_id


def test_legacy_mapping_fixture_gs014_support() -> None:
    mapped = dry_run_mapping(
        [
            ("task", "in-progress"),
            ("run", "completed"),
            ("thin_slice", "acceptance_decisions"),
        ]
    )
    assert mapped[0]["m1_value"] == "active"
    assert mapped[0]["provenance_kind"] == PROVENANCE_KIND
    assert mapped[2]["disposition"] == "unsupported"
    assert "tasks" in LEGACY_COORDINATION_TABLES


def test_representative_m0_sqlite_upgrade_preserves_ids_gs014(tmp_path) -> None:
    db = tmp_path / "legacy.db"
    store = Store(db)
    store.create_workspace({"workspace_id": "ws-alpha", "name": "Alpha"})
    task = store.create_task(
        "ws-alpha",
        {"task_id": "task-1", "title": "Legacy", "status": "in-progress"},
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    imported = import_legacy_tasks(
        conn,
        tenant_id=FixtureIds().tenant_alpha,
        actor_id=FixtureIds().system_service,
    )
    assert len(imported) == 1
    assert imported[0].legacy_task_id == task["task_id"]
    assert imported[0].legacy_status == "in-progress"
    assert imported[0].m1_state == "active"
    assert imported[0].provenance_kind == "legacy_import"
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if "gov_command_receipts" in tables:
        assert conn.execute("SELECT COUNT(*) FROM gov_command_receipts").fetchone()[0] == 0
    refreshed = Store(db).tasks("ws-alpha")
    assert any(item["task_id"] == "task-1" and item["status"] == "in-progress" for item in refreshed)


def test_legacy_upgrade_rollback_and_api_matrix_gs014(tmp_path) -> None:
    db = tmp_path / "matrix.db"
    store = Store(db)
    store.create_workspace({"workspace_id": "ws-alpha", "name": "Alpha"})
    store.create_task(
        "ws-alpha",
        {"task_id": "task-1", "title": "Legacy", "status": "ready"},
    )
    run = store.begin_run(
        "ws-alpha",
        {"task_id": "task-1", "agent_id": "codex", "claimed_paths": ["src"]},
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    ids = FixtureIds()
    migrate_governance(conn)
    assert governance_schema_version(conn) == 21
    report = import_legacy_database(
        conn, tenant_id=ids.tenant_alpha, actor_id=ids.system_service
    )
    assert len(report.workspaces) == 1
    assert len(report.tasks) == 1
    assert len(report.runs) == 1
    assert report.tasks[0].m1_state == "ready"
    assert report.runs[0].m1_state == "active"
    assert report.runs[0].legacy_run_id == run["run_id"]
    assert report.workspaces[0].provenance_kind == PROVENANCE_KIND
    # Idempotent re-import does not invent authority/receipts
    again = import_legacy_database(
        conn, tenant_id=ids.tenant_alpha, actor_id=ids.system_service
    )
    assert len(again.tasks) == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_legacy_task_imports").fetchone()[0] == 1
    # INSERT OR IGNORE leaves one row; re-import report still echoes mapped facts
    assert again.tasks[0].legacy_task_id == "task-1"
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if "gov_command_receipts" in tables:
        assert conn.execute("SELECT COUNT(*) FROM gov_command_receipts").fetchone()[0] == 0
    # Rollback of additive migrations leaves earlier gov schema intact
    rollback_governance_migration(conn, 21)
    assert governance_schema_version(conn) == 20
    rollback_governance_migration(conn, 20)
    assert governance_schema_version(conn) == 19
    rollback_governance_migration(conn, 19)
    assert governance_schema_version(conn) == 18
    rollback_governance_migration(conn, 18)
    assert governance_schema_version(conn) == 17
    rollback_governance_migration(conn, 17)
    assert governance_schema_version(conn) == 16
    rollback_governance_migration(conn, 16)
    assert governance_schema_version(conn) == 15
    rollback_governance_migration(conn, 15)
    assert governance_schema_version(conn) == 14
    rollback_governance_migration(conn, 14)
    assert governance_schema_version(conn) == 13
    rollback_governance_migration(conn, 13)
    assert governance_schema_version(conn) == 12
    rollback_governance_migration(conn, 12)
    assert governance_schema_version(conn) == 11
    rollback_governance_migration(conn, 11)
    assert governance_schema_version(conn) == 10
    rollback_governance_migration(conn, 10)
    assert governance_schema_version(conn) == 9
    rollback_governance_migration(conn, 9)
    assert governance_schema_version(conn) == 8
    rollback_governance_migration(conn, 8)
    assert governance_schema_version(conn) == 7
    rollback_governance_migration(conn, 7)
    assert governance_schema_version(conn) == 6
    rollback_governance_migration(conn, 6)
    assert governance_schema_version(conn) == 5
    rollback_governance_migration(conn, 5)
    assert governance_schema_version(conn) == 4
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "gov_command_receipts" not in tables
    assert "gov_tenants" in tables
    assert "tasks" in tables
    # Re-upgrade restores command-path tables
    migrate_governance(conn)
    assert governance_schema_version(conn) == 21
    assert "gov_command_receipts" in {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    # M0 HTTP-facing store API remains compatible after upgrade/rollback/re-upgrade
    refreshed = Store(db)
    assert refreshed.workspace("ws-alpha")["workspace_id"] == "ws-alpha"
    assert any(t["task_id"] == "task-1" for t in refreshed.tasks("ws-alpha"))
    assert any(r["run_id"] == run["run_id"] for r in refreshed.runs("ws-alpha"))
