"""M1-033: raw-SQL adversarial proofs for tenant-coupled authority references (v9)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.migrations import (
    GOVERNANCE_MIGRATIONS,
    governance_schema_version,
    migrate_governance,
    migration_now,
)
from holodeck_governance.testing import FixtureIds


STAMP = datetime(2026, 7, 24, 19, 0, tzinfo=UTC)
STAMP_ISO = STAMP.isoformat()
EXPIRES = (STAMP + timedelta(hours=2)).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _apply_through(conn: sqlite3.Connection, max_version: int) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gov_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    for version, _name, upgrade in GOVERNANCE_MIGRATIONS:
        if version > max_version:
            break
        upgrade(conn)
        conn.execute(
            "INSERT INTO gov_schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, migration_now()),
        )


def _ensure_tenant(conn: sqlite3.Connection, tenant_id: str, *, default: bool) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, ?, ?, 'm1.tenant.v1', ?, ?, NULL, 'active', ?)
        """,
        (
            tenant_id,
            f"slug-{tenant_id[-4:]}",
            f"Tenant {tenant_id[-4:]}",
            STAMP_ISO,
            "01900000-0000-7000-8000-00000000aaaa",
            1 if default else 0,
        ),
    )


def _register_object(
    conn: sqlite3.Connection, *, tenant_id: str, object_id: str, object_type: str
) -> None:
    conn.execute(
        """
        INSERT INTO gov_objects(
            object_id, tenant_id, object_type, schema_version, created_at, created_by_actor_id
        ) VALUES (?, ?, ?, 'm1.object.v1', ?, ?)
        """,
        (
            object_id,
            tenant_id,
            object_type,
            STAMP_ISO,
            "01900000-0000-7000-8000-00000000aaaa",
        ),
    )


def _insert_actor(
    conn: sqlite3.Connection, *, actor_id: str, tenant_id: str, name: str
) -> None:
    conn.execute(
        """
        INSERT INTO gov_actors(
            actor_id, tenant_id, kind, display_name, schema_version,
            created_at, created_by_actor_id
        ) VALUES (?, ?, 'human', ?, 'm1.actor.v1', ?, ?)
        """,
        (actor_id, tenant_id, name, STAMP_ISO, actor_id),
    )


def _seed_authority_world(conn: sqlite3.Connection) -> dict[str, str]:
    migrate_governance(conn)
    ids = FixtureIds()
    _ensure_tenant(conn, ids.tenant_alpha, default=True)
    _ensure_tenant(conn, ids.tenant_beta, default=False)

    alpha_subject = generate_uuidv7()
    beta_subject = generate_uuidv7()
    alpha_role = generate_uuidv7()
    beta_role = generate_uuidv7()
    for oid, tenant, kind in (
        (alpha_subject, ids.tenant_alpha, "Task"),
        (beta_subject, ids.tenant_beta, "Task"),
        (alpha_role, ids.tenant_alpha, "RoleProfile"),
        (beta_role, ids.tenant_beta, "RoleProfile"),
    ):
        _register_object(conn, tenant_id=tenant, object_id=oid, object_type=kind)

    _insert_actor(conn, actor_id=ids.human_owner, tenant_id=ids.tenant_alpha, name="Alpha Owner")
    _insert_actor(conn, actor_id=ids.worker_agent, tenant_id=ids.tenant_alpha, name="Alpha Worker")
    beta_owner = generate_uuidv7()
    beta_worker = generate_uuidv7()
    _insert_actor(conn, actor_id=beta_owner, tenant_id=ids.tenant_beta, name="Beta Owner")
    _insert_actor(conn, actor_id=beta_worker, tenant_id=ids.tenant_beta, name="Beta Worker")

    for role_id, tenant, actor in (
        (alpha_role, ids.tenant_alpha, ids.human_owner),
        (beta_role, ids.tenant_beta, beta_owner),
    ):
        conn.execute(
            """
            INSERT INTO gov_role_profiles(
                role_object_id, revision, tenant_id, name, permissions_json,
                jurisdiction_json, schema_version, created_at, created_by_actor_id
            ) VALUES (?, 1, ?, 'owner', '["transition_task"]', '{}',
                      'm1.role.v1', ?, ?)
            """,
            (role_id, tenant, STAMP_ISO, actor),
        )

    grant_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_delegated_grants(
            grant_id, tenant_id, delegator_actor_id, recipient_actor_id, permission,
            subject_object_id, subject_revision, effective_from, expires_at,
            created_at, created_by_actor_id, redelegatable, schema_version
        ) VALUES (?, ?, ?, ?, 'transition_task', ?, 1, ?, ?, ?, ?, 0, 'm1.grant.v1')
        """,
        (
            grant_id,
            ids.tenant_alpha,
            ids.human_owner,
            ids.worker_agent,
            alpha_subject,
            STAMP_ISO,
            EXPIRES,
            STAMP_ISO,
            ids.human_owner,
        ),
    )
    conn.commit()
    return {
        "alpha": ids.tenant_alpha,
        "beta": ids.tenant_beta,
        "alpha_owner": ids.human_owner,
        "alpha_worker": ids.worker_agent,
        "beta_owner": beta_owner,
        "beta_worker": beta_worker,
        "alpha_subject": alpha_subject,
        "beta_subject": beta_subject,
        "alpha_role": alpha_role,
        "beta_role": beta_role,
        "grant_id": grant_id,
    }


def test_fresh_migrate_applies_through_v9_and_installs_authority_triggers() -> None:
    conn = _connect()
    migrate_governance(conn)
    assert governance_schema_version(conn) == 14
    triggers = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    assert "gov_revocation_decisions_tenant_grant_id_ins" in triggers
    assert "gov_role_assignments_tenant_actor_id_ins" in triggers
    assert "gov_delegated_grants_tenant_delegator_actor_id_ins" in triggers
    assert "gov_delegated_grants_tenant_recipient_actor_id_ins" in triggers


def test_v8_database_upgrades_to_v9_preserving_valid_rows() -> None:
    conn = _connect()
    _apply_through(conn, 8)
    assert governance_schema_version(conn) == 8
    ids = FixtureIds()
    _ensure_tenant(conn, ids.tenant_alpha, default=True)
    _insert_actor(conn, actor_id=ids.human_owner, tenant_id=ids.tenant_alpha, name="Owner")
    _insert_actor(conn, actor_id=ids.worker_agent, tenant_id=ids.tenant_alpha, name="Worker")
    subject = generate_uuidv7()
    _register_object(conn, tenant_id=ids.tenant_alpha, object_id=subject, object_type="Task")
    grant_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_delegated_grants(
            grant_id, tenant_id, delegator_actor_id, recipient_actor_id, permission,
            subject_object_id, subject_revision, effective_from, expires_at,
            created_at, created_by_actor_id, redelegatable, schema_version
        ) VALUES (?, ?, ?, ?, 'transition_task', ?, 1, ?, ?, ?, ?, 0, 'm1.grant.v1')
        """,
        (
            grant_id,
            ids.tenant_alpha,
            ids.human_owner,
            ids.worker_agent,
            subject,
            STAMP_ISO,
            EXPIRES,
            STAMP_ISO,
            ids.human_owner,
        ),
    )
    rev_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_revocation_decisions(
            revocation_id, tenant_id, grant_id, created_at, created_by_actor_id,
            rationale, schema_version
        ) VALUES (?, ?, ?, ?, ?, 'same-tenant revoke', 'm1.revocation.v1')
        """,
        (rev_id, ids.tenant_alpha, grant_id, STAMP_ISO, ids.human_owner),
    )
    conn.commit()
    migrate_governance(conn)
    assert governance_schema_version(conn) == 14
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_revocation_decisions WHERE revocation_id = ?",
            (rev_id,),
        ).fetchone()[0]
        == 1
    )


def test_beta_cannot_insert_revocation_for_alpha_grant() -> None:
    conn = _connect()
    world = _seed_authority_world(conn)
    with pytest.raises(
        sqlite3.IntegrityError, match="cross-tenant authority reference forbidden"
    ):
        conn.execute(
            """
            INSERT INTO gov_revocation_decisions(
                revocation_id, tenant_id, grant_id, created_at, created_by_actor_id,
                rationale, schema_version
            ) VALUES (?, ?, ?, ?, ?, 'cross-tenant', 'm1.revocation.v1')
            """,
            (
                generate_uuidv7(),
                world["beta"],
                world["grant_id"],
                STAMP_ISO,
                world["beta_owner"],
            ),
        )
    assert conn.execute("SELECT COUNT(*) FROM gov_revocation_decisions").fetchone()[0] == 0


def test_beta_cannot_update_revocation_onto_alpha_grant() -> None:
    conn = _connect()
    world = _seed_authority_world(conn)
    # Same-tenant beta grant + revocation first.
    beta_grant = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_delegated_grants(
            grant_id, tenant_id, delegator_actor_id, recipient_actor_id, permission,
            subject_object_id, subject_revision, effective_from, expires_at,
            created_at, created_by_actor_id, redelegatable, schema_version
        ) VALUES (?, ?, ?, ?, 'transition_task', ?, 1, ?, ?, ?, ?, 0, 'm1.grant.v1')
        """,
        (
            beta_grant,
            world["beta"],
            world["beta_owner"],
            world["beta_worker"],
            world["beta_subject"],
            STAMP_ISO,
            EXPIRES,
            STAMP_ISO,
            world["beta_owner"],
        ),
    )
    rev_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_revocation_decisions(
            revocation_id, tenant_id, grant_id, created_at, created_by_actor_id,
            rationale, schema_version
        ) VALUES (?, ?, ?, ?, ?, 'beta revoke', 'm1.revocation.v1')
        """,
        (rev_id, world["beta"], beta_grant, STAMP_ISO, world["beta_owner"]),
    )
    conn.commit()
    with pytest.raises(
        sqlite3.IntegrityError, match="cross-tenant authority reference forbidden"
    ):
        conn.execute(
            """
            UPDATE gov_revocation_decisions
            SET grant_id = ?, tenant_id = ?
            WHERE revocation_id = ?
            """,
            (world["grant_id"], world["beta"], rev_id),
        )
    row = conn.execute(
        "SELECT grant_id, tenant_id FROM gov_revocation_decisions WHERE revocation_id = ?",
        (rev_id,),
    ).fetchone()
    assert str(row["grant_id"]) == beta_grant
    assert str(row["tenant_id"]) == world["beta"]


def test_beta_revocation_cannot_affect_alpha_authorization_defense_in_depth() -> None:
    """Plant a cross-tenant revocation under v8; tenant-scoped lookup ignores it."""

    conn = _connect()
    _apply_through(conn, 8)
    ids = FixtureIds()
    _ensure_tenant(conn, ids.tenant_alpha, default=True)
    _ensure_tenant(conn, ids.tenant_beta, default=False)
    _insert_actor(conn, actor_id=ids.human_owner, tenant_id=ids.tenant_alpha, name="Owner")
    _insert_actor(conn, actor_id=ids.worker_agent, tenant_id=ids.tenant_alpha, name="Worker")
    beta_owner = generate_uuidv7()
    _insert_actor(conn, actor_id=beta_owner, tenant_id=ids.tenant_beta, name="Beta")
    subject = generate_uuidv7()
    _register_object(conn, tenant_id=ids.tenant_alpha, object_id=subject, object_type="Task")
    grant_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_delegated_grants(
            grant_id, tenant_id, delegator_actor_id, recipient_actor_id, permission,
            subject_object_id, subject_revision, effective_from, expires_at,
            created_at, created_by_actor_id, redelegatable, schema_version
        ) VALUES (?, ?, ?, ?, 'transition_task', ?, 1, ?, ?, ?, ?, 0, 'm1.grant.v1')
        """,
        (
            grant_id,
            ids.tenant_alpha,
            ids.human_owner,
            ids.worker_agent,
            subject,
            STAMP_ISO,
            EXPIRES,
            STAMP_ISO,
            ids.human_owner,
        ),
    )
    # Pre-v9 hole: Beta revocation row referencing Alpha grant_id.
    conn.execute(
        """
        INSERT INTO gov_revocation_decisions(
            revocation_id, tenant_id, grant_id, created_at, created_by_actor_id,
            rationale, schema_version
        ) VALUES (?, ?, ?, ?, ?, 'foreign revoke', 'm1.revocation.v1')
        """,
        (generate_uuidv7(), ids.tenant_beta, grant_id, STAMP_ISO, beta_owner),
    )
    conn.commit()

    # Old grant_id-only lookup would see the Beta row.
    old = conn.execute(
        "SELECT tenant_id FROM gov_revocation_decisions WHERE grant_id = ?",
        (grant_id,),
    ).fetchone()
    assert str(old["tenant_id"]) == ids.tenant_beta

    auth = SqliteAuthorityRepository(conn)
    ok, reason = auth.actor_may_transition(
        tenant_id=ids.tenant_alpha,
        actor_id=ids.worker_agent,
        subject_object_id=subject,
        subject_revision=1,
        workspace_object_id=None,
        at=STAMP,
        permission="transition_task",
    )
    # v10 correctly fails closed: a pre-v10 grant has no inspectable issuance basis.
    assert ok is False
    assert reason == ReasonCode.DENY_MISSING_AUTHORITY.value

    migrate_governance(conn)
    assert governance_schema_version(conn) == 14
    # Existing bad row may remain; new inserts of that shape are forbidden.
    with pytest.raises(
        sqlite3.IntegrityError, match="cross-tenant authority reference forbidden"
    ):
        conn.execute(
            """
            INSERT INTO gov_revocation_decisions(
                revocation_id, tenant_id, grant_id, created_at, created_by_actor_id,
                rationale, schema_version
            ) VALUES (?, ?, ?, ?, ?, 'again', 'm1.revocation.v1')
            """,
            (generate_uuidv7(), ids.tenant_beta, grant_id, STAMP_ISO, beta_owner),
        )


def test_same_tenant_revocation_still_denies_authorization() -> None:
    conn = _connect()
    world = _seed_authority_world(conn)
    conn.execute(
        """
        INSERT INTO gov_revocation_decisions(
            revocation_id, tenant_id, grant_id, created_at, created_by_actor_id,
            rationale, schema_version
        ) VALUES (?, ?, ?, ?, ?, 'alpha revoke', 'm1.revocation.v1')
        """,
        (
            generate_uuidv7(),
            world["alpha"],
            world["grant_id"],
            STAMP_ISO,
            world["alpha_owner"],
        ),
    )
    conn.commit()
    auth = SqliteAuthorityRepository(conn)
    ok, reason = auth.actor_may_transition(
        tenant_id=world["alpha"],
        actor_id=world["alpha_worker"],
        subject_object_id=world["alpha_subject"],
        subject_revision=1,
        workspace_object_id=None,
        at=STAMP,
        permission="transition_task",
    )
    assert ok is False
    # Raw historical grant lacks the v10 issuance basis and is therefore inactive.
    assert reason == ReasonCode.DENY_MISSING_AUTHORITY.value


def test_cross_tenant_role_assignment_rejected() -> None:
    conn = _connect()
    world = _seed_authority_world(conn)
    with pytest.raises(
        sqlite3.IntegrityError, match="cross-tenant authority reference forbidden"
    ):
        conn.execute(
            """
            INSERT INTO gov_role_assignments(
                assignment_id, tenant_id, actor_id, role_object_id, role_revision,
                workspace_object_id, jurisdiction_key, jurisdiction_value,
                effective_from, effective_until, created_at, created_by_actor_id,
                schema_version
            ) VALUES (?, ?, ?, ?, 1, NULL, 'workspace', 'x', ?, NULL, ?, ?, 'm1.assignment.v1')
            """,
            (
                generate_uuidv7(),
                world["alpha"],
                world["beta_worker"],
                world["alpha_role"],
                STAMP_ISO,
                STAMP_ISO,
                world["alpha_owner"],
            ),
        )


def test_cross_tenant_delegation_rejected() -> None:
    conn = _connect()
    world = _seed_authority_world(conn)
    with pytest.raises(
        sqlite3.IntegrityError, match="cross-tenant authority reference forbidden"
    ):
        conn.execute(
            """
            INSERT INTO gov_delegated_grants(
                grant_id, tenant_id, delegator_actor_id, recipient_actor_id, permission,
                subject_object_id, subject_revision, effective_from, expires_at,
                created_at, created_by_actor_id, redelegatable, schema_version
            ) VALUES (?, ?, ?, ?, 'transition_task', ?, 1, ?, ?, ?, ?, 0, 'm1.grant.v1')
            """,
            (
                generate_uuidv7(),
                world["alpha"],
                world["alpha_owner"],
                world["beta_worker"],
                world["alpha_subject"],
                STAMP_ISO,
                EXPIRES,
                STAMP_ISO,
                world["alpha_owner"],
            ),
        )


def test_same_tenant_role_assignment_and_grant_succeed() -> None:
    conn = _connect()
    world = _seed_authority_world(conn)
    assignment_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_role_assignments(
            assignment_id, tenant_id, actor_id, role_object_id, role_revision,
            workspace_object_id, jurisdiction_key, jurisdiction_value,
            effective_from, effective_until, created_at, created_by_actor_id,
            schema_version
        ) VALUES (?, ?, ?, ?, 1, NULL, 'workspace', 'x', ?, NULL, ?, ?, 'm1.assignment.v1')
        """,
        (
            assignment_id,
            world["alpha"],
            world["alpha_worker"],
            world["alpha_role"],
            STAMP_ISO,
            STAMP_ISO,
            world["alpha_owner"],
        ),
    )
    grant_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_delegated_grants(
            grant_id, tenant_id, delegator_actor_id, recipient_actor_id, permission,
            subject_object_id, subject_revision, effective_from, expires_at,
            created_at, created_by_actor_id, redelegatable, schema_version
        ) VALUES (?, ?, ?, ?, 'transition_task', ?, 1, ?, ?, ?, ?, 0, 'm1.grant.v1')
        """,
        (
            grant_id,
            world["beta"],
            world["beta_owner"],
            world["beta_worker"],
            world["beta_subject"],
            STAMP_ISO,
            EXPIRES,
            STAMP_ISO,
            world["beta_owner"],
        ),
    )
    conn.commit()
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_role_assignments WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_delegated_grants WHERE grant_id = ?",
            (grant_id,),
        ).fetchone()[0]
        == 1
    )
