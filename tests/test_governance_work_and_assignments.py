"""Tests for typed work vocabulary and role assignments."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from holodeck_governance.domain.authority.assignments import (
    RoleAssignment,
    reject_cross_tenant_assignment,
    resolve_assignment,
)
from holodeck_governance.domain.errors import CrossTenantAccessError, MissingAuthorityError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records import (
    IntentRecord,
    MissionRecord,
    SourceRecord,
    TaskRecord,
    WorkspaceRecord,
    hash_mission,
    hash_workspace,
)
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.tenant import assert_same_tenant
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FixtureIds


def test_work_records_use_relational_object_links_not_json_ownership() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    workspace = WorkspaceRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=ids.workspace_alpha_1,
        revision=1,
        name="Alpha",
        created_at=now,
        created_by_actor_id=ids.human_owner,
        content_hash="pending",
    )
    workspace = replace(workspace, content_hash=hash_workspace(workspace))
    source = SourceRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=generate_uuidv7(),
        revision=1,
        workspace_object_id=workspace.object_id,
        kind="repo",
        locator="git://example",
        created_at=now,
        created_by_actor_id=ids.human_owner,
        content_hash="sha256:source",
    )
    intent = IntentRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=generate_uuidv7(),
        revision=1,
        workspace_object_id=workspace.object_id,
        statement="Ship governance kernel",
        created_at=now,
        created_by_actor_id=ids.human_owner,
        content_hash="sha256:intent",
    )
    mission = MissionRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=ids.mission_object,
        revision=1,
        workspace_object_id=workspace.object_id,
        intent_object_id=intent.object_id,
        summary="M1 kernel",
        created_at=now,
        created_by_actor_id=ids.human_owner,
        content_hash="pending",
    )
    mission = replace(mission, content_hash=hash_mission(mission))
    task = TaskRecord(
        record_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        object_id=generate_uuidv7(),
        revision=1,
        workspace_object_id=workspace.object_id,
        mission_object_id=mission.object_id,
        title="Implement records",
        state="draft",
        created_at=now,
        created_by_actor_id=ids.human_owner,
        content_hash="sha256:task",
    )
    assert source.workspace_object_id == workspace.object_id
    assert mission.intent_object_id == intent.object_id
    assert task.mission_object_id == mission.object_id
    with pytest.raises(CrossTenantAccessError):
        assert_same_tenant(
            actor_tenant_id=ids.tenant_alpha,
            record_tenant_id=ids.tenant_beta,
            context="mission",
        )


def test_work_vocabulary_tables_migrate() -> None:
    conn = sqlite3.connect(":memory:")
    ensure_default_local_tenant(
        conn,
        tenant_id=FixtureIds().tenant_alpha,
        created_by_actor_id=FixtureIds().system_service,
    )
    migrate_governance(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {
        "gov_workspaces",
        "gov_sources",
        "gov_intents",
        "gov_missions",
        "gov_tasks",
    } <= tables
    repo = SqliteRevisionRepository(conn)
    obj = GovernanceObject(
        object_id=FixtureIds().workspace_alpha_1,
        tenant_id=FixtureIds().tenant_alpha,
        object_type="Workspace",
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=FixtureIds().human_owner,
    )
    repo.register_object(obj)
    conn.execute(
        """
        INSERT INTO gov_workspaces(
            record_id, tenant_id, object_id, revision, name, status, content_hash,
            schema_version, created_at, created_by_actor_id
        ) VALUES (?, ?, ?, 1, 'Alpha', 'active', 'sha256:x', 'm1.workspace.v1', ?, ?)
        """,
        (
            generate_uuidv7(),
            FixtureIds().tenant_alpha,
            FixtureIds().workspace_alpha_1,
            datetime(2026, 7, 24, 12, 0, tzinfo=UTC).isoformat(),
            FixtureIds().human_owner,
        ),
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM gov_workspaces").fetchone()[0]
    assert count == 1


def test_work_family_write_repos_persist() -> None:
    from holodeck_governance.storage.sqlite.records import SqliteRecordRepository
    from holodeck_governance.storage.sqlite.tasks import SqliteTaskRepository

    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    records = SqliteRecordRepository(conn)
    workspace = records.save_workspace(
        WorkspaceRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=ids.workspace_alpha_1,
            revision=1,
            name="Alpha",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    intent = records.save_intent(
        IntentRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=generate_uuidv7(),
            revision=1,
            workspace_object_id=workspace.object_id,
            statement="Ship kernel",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    records.save_source(
        SourceRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=generate_uuidv7(),
            revision=1,
            workspace_object_id=workspace.object_id,
            kind="repo",
            locator="git://example",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    mission = records.save_mission(
        MissionRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=ids.mission_object,
            revision=1,
            workspace_object_id=workspace.object_id,
            intent_object_id=intent.object_id,
            summary="M1",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    SqliteTaskRepository(conn).create_task(
        TaskRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=generate_uuidv7(),
            revision=1,
            workspace_object_id=workspace.object_id,
            mission_object_id=mission.object_id,
            title="Work",
            state="draft",
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    assert conn.execute("SELECT COUNT(*) FROM gov_workspaces").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_sources").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_intents").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_missions").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM gov_tasks").fetchone()[0] == 1


def test_role_assignment_matrix_time_and_jurisdiction() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    active = RoleAssignment(
        assignment_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        actor_id=ids.human_reviewer,
        role_object_id=generate_uuidv7(),
        role_revision=1,
        workspace_object_id=ids.workspace_alpha_1,
        jurisdiction_key="workspace",
        jurisdiction_value=ids.workspace_alpha_1,
        effective_from=now - timedelta(hours=1),
        effective_until=now + timedelta(hours=1),
        created_at=now,
        created_by_actor_id=ids.system_service,
    )
    expired = RoleAssignment(
        assignment_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        actor_id=ids.human_reviewer,
        role_object_id=active.role_object_id,
        role_revision=1,
        workspace_object_id=ids.workspace_alpha_1,
        jurisdiction_key="workspace",
        jurisdiction_value=ids.workspace_alpha_1,
        effective_from=now - timedelta(days=2),
        effective_until=now - timedelta(days=1),
        created_at=now,
        created_by_actor_id=ids.system_service,
    )
    resolved = resolve_assignment(
        [expired, active],
        actor_id=ids.human_reviewer,
        tenant_id=ids.tenant_alpha,
        jurisdiction_key="workspace",
        jurisdiction_value=ids.workspace_alpha_1,
        at=now,
    )
    assert resolved.assignment_id == active.assignment_id
    with pytest.raises(MissingAuthorityError):
        resolve_assignment(
            [expired],
            actor_id=ids.human_reviewer,
            tenant_id=ids.tenant_alpha,
            jurisdiction_key="workspace",
            jurisdiction_value=ids.workspace_alpha_1,
            at=now,
        )
    with pytest.raises(CrossTenantAccessError):
        reject_cross_tenant_assignment(active, ids.tenant_beta)
