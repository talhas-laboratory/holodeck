"""Seed helpers that create durable governed records for command-path tests."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.assignments import RoleAssignment
from holodeck_governance.domain.authority.roles import RoleProfile
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records.task import TaskRecord
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tasks import SqliteTaskRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FixtureIds, FIXED_CLOCK


def seed_authorized_task_world(
    conn: sqlite3.Connection,
    *,
    ids: FixtureIds | None = None,
    task_state: str = "draft",
    permissions: tuple[str, ...] = ("transition_task",),
    clock: datetime | None = None,
) -> dict[str, str]:
    """Create tenant, actor, role assignment, workspace/mission placeholders, and task."""

    ids = ids or FixtureIds()
    now = clock or FIXED_CLOCK
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    auth = SqliteAuthorityRepository(conn)
    revisions = SqliteRevisionRepository(conn)
    tasks = SqliteTaskRepository(conn)

    auth.save_actor(
        Actor(
            actor_id=ids.human_owner,
            tenant_id=ids.tenant_alpha,
            kind=ActorKind.HUMAN,
            display_name="Owner",
            created_at=now,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_actor(
        Actor(
            actor_id=ids.system_service,
            tenant_id=ids.tenant_alpha,
            kind=ActorKind.SERVICE,
            display_name="System",
            created_at=now,
            created_by_actor_id=ids.system_service,
        )
    )

    role_object_id = generate_uuidv7()
    revisions.register_object(
        GovernanceObject(
            object_id=role_object_id,
            tenant_id=ids.tenant_alpha,
            object_type="RoleProfile",
            created_at=now,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_role_profile(
        RoleProfile(
            role_profile_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            role_object_id=role_object_id,
            revision=1,
            name="owner",
            permissions=permissions,
            jurisdiction={"workspace": ids.workspace_alpha_1},
            created_at=now,
            created_by_actor_id=ids.system_service,
        )
    )

    # Workspace + mission objects for FK targets
    for object_id, object_type in (
        (ids.workspace_alpha_1, "Workspace"),
        (ids.mission_object, "Mission"),
    ):
        if revisions.get_object(object_id) is None:
            revisions.register_object(
                GovernanceObject(
                    object_id=object_id,
                    tenant_id=ids.tenant_alpha,
                    object_type=object_type,
                    created_at=now,
                    created_by_actor_id=ids.system_service,
                )
            )
            from holodeck_governance.domain.revisions import ObjectRevision, content_hash_for

            rev = ObjectRevision(
                revision_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                object_id=object_id,
                revision=1,
                content_hash=content_hash_for({"kind": object_type}),
                payload={"kind": object_type},
                created_at=now,
                created_by_actor_id=ids.system_service,
                finalized=True,
            )
            revisions._insert_revision(rev)
            revisions._upsert_head(rev)

    role_assignment_id = generate_uuidv7()
    auth.save_assignment(
        RoleAssignment(
            assignment_id=role_assignment_id,
            tenant_id=ids.tenant_alpha,
            actor_id=ids.human_owner,
            role_object_id=role_object_id,
            role_revision=1,
            workspace_object_id=ids.workspace_alpha_1,
            jurisdiction_key="workspace",
            jurisdiction_value=ids.workspace_alpha_1,
            effective_from=now - timedelta(hours=1),
            created_at=now,
            created_by_actor_id=ids.system_service,
            effective_until=now + timedelta(days=30),
        )
    )

    task_object_id = generate_uuidv7()
    tasks.create_task(
        TaskRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=task_object_id,
            revision=1,
            workspace_object_id=ids.workspace_alpha_1,
            mission_object_id=ids.mission_object,
            title="Seeded task",
            state=task_state,
            created_at=now,
            created_by_actor_id=ids.human_owner,
        )
    )
    conn.commit()
    return {
        "tenant_id": ids.tenant_alpha,
        "actor_id": ids.human_owner,
        "task_object_id": task_object_id,
        "workspace_object_id": ids.workspace_alpha_1,
        "mission_object_id": ids.mission_object,
        "role_object_id": role_object_id,
        "role_assignment_id": role_assignment_id,
    }


def seed_authorized_run_world(
    conn: sqlite3.Connection,
    *,
    ids: FixtureIds | None = None,
    run_state: str = "created",
    clock: datetime | None = None,
) -> dict[str, str]:
    """Seed a task world plus a Run head for run.transition commands."""

    from holodeck_governance.domain.records.run import RunRecord
    from holodeck_governance.storage.sqlite.runs import SqliteRunRepository

    world = seed_authorized_task_world(
        conn,
        ids=ids,
        task_state="active",
        permissions=("transition_task", "transition_run"),
        clock=clock,
    )
    now = clock or FIXED_CLOCK
    run_object_id = generate_uuidv7()
    SqliteRunRepository(conn).create_run(
        RunRecord(
            record_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            object_id=run_object_id,
            revision=1,
            task_object_id=world["task_object_id"],
            mission_object_id=world["mission_object_id"],
            state=run_state,
            created_at=now,
            created_by_actor_id=world["actor_id"],
        )
    )
    conn.commit()
    world["run_object_id"] = run_object_id
    return world
