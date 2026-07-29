"""Adversarial proofs for release-blocking M1 enforcement (run 7)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from holodeck_governance.domain.catalogs.events import EVENT_ENVELOPE_FIELDS, EventType
from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.commands import CommandEnvelope
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.policy.binding import PolicyBinding
from holodeck_governance.domain.records.review import ApprovalRecord
from holodeck_governance.domain.records.source import SourceRecord
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.command_service import CommandService
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.policy import SqlitePolicyRepository
from holodeck_governance.storage.sqlite.records import SqliteRecordRepository
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FixtureIds
from holodeck_governance.testing.seed import seed_authorized_task_world


def _cmd(world: dict[str, str], **overrides) -> CommandEnvelope:
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


def test_required_approvals_two_rejects_single_approval() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(
        conn, permissions=("transition_task", "approve")
    )
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    SqlitePolicyRepository(conn).save(
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            scope="tenant",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "2"},
            created_at=now,
            created_by_actor_id=world["actor_id"],
            precedence=10,
            effective_from=now,
        )
    )
    SqliteAuthorityRepository(conn).save_approval(
        ApprovalRecord(
            record_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            object_id=generate_uuidv7(),
            revision=1,
            subject_object_id=world["task_object_id"],
            subject_revision=1,
            created_at=now,
            created_by_actor_id=world["actor_id"],
            decision="approved",
        )
    )
    conn.commit()
    receipt = CommandService(conn).handle(_cmd(world, idempotency_key="need-two"))
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_STALE_APPROVAL.value in receipt.reason_codes
    task_state = conn.execute(
        "SELECT state FROM gov_tasks WHERE object_id = ? ORDER BY revision DESC LIMIT 1",
        (world["task_object_id"],),
    ).fetchone()[0]
    assert task_state == "draft"


def test_duplicate_approver_does_not_satisfy_cardinality() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(
        conn, permissions=("transition_task", "approve")
    )
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    SqlitePolicyRepository(conn).save(
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            scope="tenant",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "2"},
            created_at=now,
            created_by_actor_id=world["actor_id"],
            precedence=10,
            effective_from=now,
        )
    )
    auth = SqliteAuthorityRepository(conn)
    for _ in range(2):
        auth.save_approval(
            ApprovalRecord(
                record_id=generate_uuidv7(),
                tenant_id=world["tenant_id"],
                object_id=generate_uuidv7(),
                revision=1,
                subject_object_id=world["task_object_id"],
                subject_revision=1,
                created_at=now,
                created_by_actor_id=world["actor_id"],
                decision="approved",
            )
        )
    conn.commit()
    receipt = CommandService(conn).handle(_cmd(world, idempotency_key="dup-approver"))
    assert receipt.outcome == "rejected"


def test_cross_tenant_typed_reference_rejected() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    # Second tenant
    conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'beta', 'Beta', 'm1.tenant.v1', ?, ?, NULL, 'active', 0)
        """,
        (ids.tenant_beta, now.isoformat(), ids.system_service),
    )
    revisions = SqliteRevisionRepository(conn)
    beta_workspace = generate_uuidv7()
    revisions.register_object(
        GovernanceObject(
            object_id=beta_workspace,
            tenant_id=ids.tenant_beta,
            object_type="Workspace",
            created_at=now,
            created_by_actor_id=ids.system_service,
        )
    )
    source_object = generate_uuidv7()
    with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
        SqliteRecordRepository(conn).save_source(
            SourceRecord(
                record_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                object_id=source_object,
                revision=1,
                workspace_object_id=beta_workspace,
                kind="repo",
                locator="https://example.invalid/beta",
                created_at=now,
                created_by_actor_id=ids.system_service,
            )
        )


def test_finalized_revision_db_immutable() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    CommandService(conn).handle(_cmd(world, idempotency_key="rev-1"))
    row = conn.execute(
        """
        SELECT revision_id, payload_json FROM gov_object_revisions
        WHERE object_id = ? AND finalized = 1
        ORDER BY revision DESC LIMIT 1
        """,
        (world["task_object_id"],),
    ).fetchone()
    assert row is not None
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute(
            "UPDATE gov_object_revisions SET payload_json = ? WHERE revision_id = ?",
            ('{"tampered": true}', row["revision_id"]),
        )


def test_emitted_events_include_catalog_envelope_fields() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    CommandService(conn).handle(_cmd(world, idempotency_key="evt-1"))
    event = conn.execute(
        "SELECT * FROM gov_domain_events ORDER BY ledger_sequence DESC LIMIT 1"
    ).fetchone()
    assert event is not None
    assert event["event_type"] == EventType.COMMAND_ACCEPTED.value
    assert event["actor_id"] == world["actor_id"]
    assert event["payload_schema_version"] == "m1.event.command_accepted.v1"
    assert event["occurred_at"]
    assert event["subject_object_id"] == world["task_object_id"]
    assert event["subject_revision"] == 1
    # Envelope columns present on the row
    for field in (
        "event_id",
        "tenant_id",
        "ledger_sequence",
        "event_type",
        "occurred_at",
        "actor_id",
        "correlation_id",
        "causation_id",
        "payload_schema_version",
    ):
        assert event[field] is not None, field
    assert "subject_refs" in EVENT_ENVELOPE_FIELDS
    refs = json.loads(str(event["subject_refs_json"]))
    assert refs["subject_object_id"] == world["task_object_id"]


def test_adapter_uses_application_composition_not_sqlite_direct() -> None:
    import ast
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "holodeck_control_plane"
        / "governance_commands.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert "holodeck_governance.composition" in modules
    assert "holodeck_governance.storage.sqlite.command_service" not in modules


def test_migrate_v10_applies() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    version = conn.execute(
        "SELECT MAX(version) FROM gov_schema_migrations"
    ).fetchone()[0]
    assert int(version) == 22
    cols = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(gov_domain_events)").fetchall()
    }
    assert "actor_id" in cols
    assert "payload_schema_version" in cols
    triggers = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    assert "gov_sources_tenant_object_id_ins" in triggers
    assert "gov_revocation_decisions_tenant_grant_id_ins" in triggers
