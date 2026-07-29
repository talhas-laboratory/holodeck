"""M1-032: raw-SQL adversarial proofs for tenant-coupled object ownership (v8)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.storage.sqlite.migrations import (
    GOVERNANCE_MIGRATIONS,
    governance_schema_version,
    migrate_governance,
    migration_now,
)
from holodeck_governance.storage.sqlite.migrate_v8 import upgrade_tenant_coupled_ownership
from holodeck_governance.testing import FixtureIds


STAMP = datetime(2026, 7, 24, 18, 0, tzinfo=UTC).isoformat()
ACTOR = "01900000-0000-7000-8000-00000000aaaa"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
            STAMP,
            ACTOR,
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
        (object_id, tenant_id, object_type, STAMP, ACTOR),
    )


def _seed_two_tenants(conn: sqlite3.Connection) -> dict[str, str]:
    migrate_governance(conn)
    ids = FixtureIds()
    _ensure_tenant(conn, ids.tenant_alpha, default=True)
    _ensure_tenant(conn, ids.tenant_beta, default=False)
    alpha_obj = generate_uuidv7()
    beta_obj = generate_uuidv7()
    alpha_ws = generate_uuidv7()
    beta_ws = generate_uuidv7()
    for oid, tenant, kind in (
        (alpha_obj, ids.tenant_alpha, "Source"),
        (beta_obj, ids.tenant_beta, "Source"),
        (alpha_ws, ids.tenant_alpha, "Workspace"),
        (beta_ws, ids.tenant_beta, "Workspace"),
    ):
        _register_object(conn, tenant_id=tenant, object_id=oid, object_type=kind)
    conn.commit()
    return {
        "alpha": ids.tenant_alpha,
        "beta": ids.tenant_beta,
        "alpha_obj": alpha_obj,
        "beta_obj": beta_obj,
        "alpha_ws": alpha_ws,
        "beta_ws": beta_ws,
    }


def test_fresh_migrate_applies_through_v8_and_installs_identity_triggers() -> None:
    conn = _connect()
    migrate_governance(conn)
    assert governance_schema_version(conn) == 16
    triggers = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    assert "gov_sources_tenant_object_id_ins" in triggers
    assert "gov_object_revisions_tenant_object_id_ins" in triggers
    assert "gov_object_heads_tenant_object_id_ins" in triggers
    assert "gov_missions_tenant_intent_object_id_ins" in triggers
    assert "gov_role_assignments_tenant_role_object_id_ins" in triggers
    assert "gov_domain_events_tenant_subject_object_id_ins" in triggers
    assert "gov_object_heads_revision_consistency_ins" in triggers


def test_v7_database_upgrades_to_v8_preserving_valid_rows() -> None:
    conn = _connect()
    # Apply through v7 only.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gov_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    for version, _name, upgrade in GOVERNANCE_MIGRATIONS:
        if version > 7:
            break
        upgrade(conn)
        conn.execute(
            "INSERT INTO gov_schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, migration_now()),
        )
    assert governance_schema_version(conn) == 7
    ids = FixtureIds()
    _ensure_tenant(conn, ids.tenant_alpha, default=True)
    obj = generate_uuidv7()
    _register_object(conn, tenant_id=ids.tenant_alpha, object_id=obj, object_type="Workspace")
    conn.execute(
        """
        INSERT INTO gov_workspaces(
            record_id, tenant_id, object_id, revision, name, status,
            content_hash, schema_version, created_at, created_by_actor_id
        ) VALUES (?, ?, ?, 1, 'Alpha WS', 'active', 'sha256:x', 'm1.workspace.v1', ?, ?)
        """,
        (generate_uuidv7(), ids.tenant_alpha, obj, STAMP, ACTOR),
    )
    conn.commit()
    migrate_governance(conn)
    assert governance_schema_version(conn) == 16
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_workspaces WHERE object_id = ?", (obj,)
        ).fetchone()[0]
        == 1
    )


def test_alpha_source_tenant_with_beta_object_id_rejected() -> None:
    conn = _connect()
    world = _seed_two_tenants(conn)
    with pytest.raises(sqlite3.IntegrityError, match="cross-tenant reference forbidden"):
        conn.execute(
            """
            INSERT INTO gov_sources(
                record_id, tenant_id, object_id, revision, workspace_object_id,
                kind, locator, provenance_ref, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, ?, 'repo', 'loc', NULL, 'sha256:x',
                      'm1.source.v1', ?, ?)
            """,
            (
                generate_uuidv7(),
                world["alpha"],
                world["beta_obj"],
                world["alpha_ws"],
                STAMP,
                ACTOR,
            ),
        )
    assert conn.execute("SELECT COUNT(*) FROM gov_sources").fetchone()[0] == 0


def test_alpha_revision_with_beta_object_id_rejected() -> None:
    conn = _connect()
    world = _seed_two_tenants(conn)
    with pytest.raises(sqlite3.IntegrityError, match="cross-tenant reference forbidden"):
        conn.execute(
            """
            INSERT INTO gov_object_revisions(
                revision_id, tenant_id, object_id, revision, supersedes_revision,
                content_hash, payload_json, finalized, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, NULL, 'sha256:x', '{}', 0, 'm1.revision.v1', ?, ?)
            """,
            (generate_uuidv7(), world["alpha"], world["beta_obj"], STAMP, ACTOR),
        )


def test_alpha_head_with_beta_object_id_rejected() -> None:
    conn = _connect()
    world = _seed_two_tenants(conn)
    # Valid alpha revision for head_revision_id FK, but head claims beta object.
    rev_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_object_revisions(
            revision_id, tenant_id, object_id, revision, supersedes_revision,
            content_hash, payload_json, finalized, schema_version,
            created_at, created_by_actor_id
        ) VALUES (?, ?, ?, 1, NULL, 'sha256:x', '{}', 1, 'm1.revision.v1', ?, ?)
        """,
        (rev_id, world["alpha"], world["alpha_obj"], STAMP, ACTOR),
    )
    with pytest.raises(sqlite3.IntegrityError, match="cross-tenant reference forbidden"):
        conn.execute(
            """
            INSERT INTO gov_object_heads(
                object_id, tenant_id, head_revision, head_revision_id
            ) VALUES (?, ?, 1, ?)
            """,
            (world["beta_obj"], world["alpha"], rev_id),
        )


def test_alpha_mission_with_beta_intent_rejected() -> None:
    conn = _connect()
    world = _seed_two_tenants(conn)
    mission_obj = generate_uuidv7()
    _register_object(
        conn, tenant_id=world["alpha"], object_id=mission_obj, object_type="Mission"
    )
    intent_beta = generate_uuidv7()
    _register_object(
        conn, tenant_id=world["beta"], object_id=intent_beta, object_type="Intent"
    )
    with pytest.raises(sqlite3.IntegrityError, match="cross-tenant reference forbidden"):
        conn.execute(
            """
            INSERT INTO gov_missions(
                record_id, tenant_id, object_id, revision, workspace_object_id,
                intent_object_id, summary, status, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, ?, ?, 's', 'active', 'sha256:x', 'm1.mission.v1', ?, ?)
            """,
            (
                generate_uuidv7(),
                world["alpha"],
                mission_obj,
                world["alpha_ws"],
                intent_beta,
                STAMP,
                ACTOR,
            ),
        )


def test_alpha_role_assignment_with_beta_role_rejected() -> None:
    conn = _connect()
    world = _seed_two_tenants(conn)
    # Actors + beta role profile (FK target), then alpha assignment to beta role.
    for tenant in (world["alpha"], world["beta"]):
        conn.execute(
            """
            INSERT OR IGNORE INTO gov_actors(
                actor_id, tenant_id, kind, display_name, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, 'human', 'A', 'm1.actor.v1', ?, ?)
            """,
            (ACTOR if tenant == world["alpha"] else generate_uuidv7(), tenant, STAMP, ACTOR),
        )
    beta_role = generate_uuidv7()
    _register_object(
        conn, tenant_id=world["beta"], object_id=beta_role, object_type="RoleProfile"
    )
    conn.execute(
        """
        INSERT INTO gov_role_profiles(
            role_object_id, revision, tenant_id, name, permissions_json,
            jurisdiction_json, schema_version, created_at, created_by_actor_id
        ) VALUES (?, 1, ?, 'beta-role', '["*"]', '{}', 'm1.role_profile.v1', ?, ?)
        """,
        (beta_role, world["beta"], STAMP, ACTOR),
    )
    alpha_actor = ACTOR
    with pytest.raises(sqlite3.IntegrityError, match="cross-tenant reference forbidden"):
        conn.execute(
            """
            INSERT INTO gov_role_assignments(
                assignment_id, tenant_id, actor_id, role_object_id, role_revision,
                workspace_object_id, jurisdiction_key, jurisdiction_value,
                effective_from, effective_until, created_at, created_by_actor_id,
                schema_version
            ) VALUES (?, ?, ?, ?, 1, ?, 'workspace', ?, ?, NULL, ?, ?, 'm1.role_assignment.v1')
            """,
            (
                generate_uuidv7(),
                world["alpha"],
                alpha_actor,
                beta_role,
                world["alpha_ws"],
                world["alpha_ws"],
                STAMP,
                STAMP,
                ACTOR,
            ),
        )


def test_alpha_event_with_beta_subject_rejected() -> None:
    conn = _connect()
    world = _seed_two_tenants(conn)
    with pytest.raises(sqlite3.IntegrityError, match="cross-tenant reference forbidden"):
        conn.execute(
            """
            INSERT INTO gov_domain_events(
                event_id, tenant_id, ledger_sequence, event_type, payload_json,
                correlation_id, causation_id, created_at, actor_id,
                payload_schema_version, occurred_at, subject_object_id,
                subject_revision, subject_refs_json
            ) VALUES (?, ?, 1, 'governance.command.accepted', '{}', ?, ?, ?, ?,
                      'm1.event.command_accepted.v1', ?, ?, 1, '{}')
            """,
            (
                generate_uuidv7(),
                world["alpha"],
                generate_uuidv7(),
                generate_uuidv7(),
                STAMP,
                ACTOR,
                STAMP,
                world["beta_obj"],
            ),
        )


@pytest.mark.parametrize(
    "case",
    [
        "sources_object_id",
        "revisions_object_id",
        "heads_object_id",
        "workspaces_object_id",
        "missions_intent",
        "role_assignments_role",
        "events_subject",
        "evaluation_snapshots_subject",
        "transition_records_subject",
        "command_subject_links_subject",
        "test_plans_mission",
    ],
)
def test_parameterized_tenant_coupling_insert_update(case: str) -> None:
    conn = _connect()
    world = _seed_two_tenants(conn)
    alpha = world["alpha"]
    beta = world["beta"]

    def count(table: str) -> int:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    if case == "sources_object_id":
        table = "gov_sources"
        good_obj = generate_uuidv7()
        _register_object(conn, tenant_id=alpha, object_id=good_obj, object_type="Source")
        good_sql = """
            INSERT INTO gov_sources(
                record_id, tenant_id, object_id, revision, workspace_object_id,
                kind, locator, provenance_ref, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, ?, 'repo', 'loc', NULL, 'sha256:x',
                      'm1.source.v1', ?, ?)
        """
        good_params = (generate_uuidv7(), alpha, good_obj, world["alpha_ws"], STAMP, ACTOR)
        conn.execute(good_sql, good_params)
        before = count(table)
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                good_sql,
                (generate_uuidv7(), alpha, world["beta_obj"], world["alpha_ws"], STAMP, ACTOR),
            )
        assert count(table) == before
        record_id = good_params[0]
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                "UPDATE gov_sources SET object_id = ? WHERE record_id = ?",
                (world["beta_obj"], record_id),
            )
        assert (
            conn.execute(
                "SELECT object_id FROM gov_sources WHERE record_id = ?", (record_id,)
            ).fetchone()[0]
            == good_obj
        )
        return

    if case == "revisions_object_id":
        table = "gov_object_revisions"
        good_sql = """
            INSERT INTO gov_object_revisions(
                revision_id, tenant_id, object_id, revision, supersedes_revision,
                content_hash, payload_json, finalized, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, NULL, 'sha256:x', '{}', 0, 'm1.revision.v1', ?, ?)
        """
        rid = generate_uuidv7()
        conn.execute(good_sql, (rid, alpha, world["alpha_obj"], STAMP, ACTOR))
        before = count(table)
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                good_sql,
                (generate_uuidv7(), alpha, world["beta_obj"], STAMP, ACTOR),
            )
        assert count(table) == before
        # Non-finalized row can be updated; cross-tenant must fail via v8 trigger.
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                "UPDATE gov_object_revisions SET object_id = ? WHERE revision_id = ?",
                (world["beta_obj"], rid),
            )
        assert (
            conn.execute(
                "SELECT object_id FROM gov_object_revisions WHERE revision_id = ?",
                (rid,),
            ).fetchone()[0]
            == world["alpha_obj"]
        )
        return

    if case == "heads_object_id":
        rev_id = generate_uuidv7()
        conn.execute(
            """
            INSERT INTO gov_object_revisions(
                revision_id, tenant_id, object_id, revision, supersedes_revision,
                content_hash, payload_json, finalized, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, NULL, 'sha256:x', '{}', 1, 'm1.revision.v1', ?, ?)
            """,
            (rev_id, alpha, world["alpha_obj"], STAMP, ACTOR),
        )
        conn.execute(
            """
            INSERT INTO gov_object_heads(object_id, tenant_id, head_revision, head_revision_id)
            VALUES (?, ?, 1, ?)
            """,
            (world["alpha_obj"], alpha, rev_id),
        )
        before = count("gov_object_heads")
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_object_heads(object_id, tenant_id, head_revision, head_revision_id)
                VALUES (?, ?, 1, ?)
                """,
                (world["beta_obj"], alpha, rev_id),
            )
        assert count("gov_object_heads") == before
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                "UPDATE gov_object_heads SET object_id = ? WHERE object_id = ?",
                (world["beta_obj"], world["alpha_obj"]),
            )
        assert (
            conn.execute(
                "SELECT object_id FROM gov_object_heads WHERE head_revision_id = ?",
                (rev_id,),
            ).fetchone()[0]
            == world["alpha_obj"]
        )
        return

    if case == "workspaces_object_id":
        good_obj = generate_uuidv7()
        _register_object(conn, tenant_id=alpha, object_id=good_obj, object_type="Workspace")
        rid = generate_uuidv7()
        conn.execute(
            """
            INSERT INTO gov_workspaces(
                record_id, tenant_id, object_id, revision, name, status,
                content_hash, schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, 'ok', 'active', 'sha256:x', 'm1.workspace.v1', ?, ?)
            """,
            (rid, alpha, good_obj, STAMP, ACTOR),
        )
        before = count("gov_workspaces")
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_workspaces(
                    record_id, tenant_id, object_id, revision, name, status,
                    content_hash, schema_version, created_at, created_by_actor_id
                ) VALUES (?, ?, ?, 1, 'bad', 'active', 'sha256:x', 'm1.workspace.v1', ?, ?)
                """,
                (generate_uuidv7(), alpha, world["beta_obj"], STAMP, ACTOR),
            )
        assert count("gov_workspaces") == before
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                "UPDATE gov_workspaces SET object_id = ? WHERE record_id = ?",
                (world["beta_obj"], rid),
            )
        assert (
            conn.execute(
                "SELECT object_id FROM gov_workspaces WHERE record_id = ?", (rid,)
            ).fetchone()[0]
            == good_obj
        )
        return

    if case == "missions_intent":
        mission_obj = generate_uuidv7()
        intent_alpha = generate_uuidv7()
        intent_beta = generate_uuidv7()
        _register_object(conn, tenant_id=alpha, object_id=mission_obj, object_type="Mission")
        _register_object(conn, tenant_id=alpha, object_id=intent_alpha, object_type="Intent")
        _register_object(conn, tenant_id=beta, object_id=intent_beta, object_type="Intent")
        rid = generate_uuidv7()
        conn.execute(
            """
            INSERT INTO gov_missions(
                record_id, tenant_id, object_id, revision, workspace_object_id,
                intent_object_id, summary, status, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, ?, ?, 's', 'active', 'sha256:x', 'm1.mission.v1', ?, ?)
            """,
            (rid, alpha, mission_obj, world["alpha_ws"], intent_alpha, STAMP, ACTOR),
        )
        before = count("gov_missions")
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_missions(
                    record_id, tenant_id, object_id, revision, workspace_object_id,
                    intent_object_id, summary, status, content_hash, schema_version,
                    created_at, created_by_actor_id
                ) VALUES (?, ?, ?, 1, ?, ?, 's', 'active', 'sha256:x', 'm1.mission.v1', ?, ?)
                """,
                (
                    generate_uuidv7(),
                    alpha,
                    mission_obj,
                    world["alpha_ws"],
                    intent_beta,
                    STAMP,
                    ACTOR,
                ),
            )
        assert count("gov_missions") == before
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                "UPDATE gov_missions SET intent_object_id = ? WHERE record_id = ?",
                (intent_beta, rid),
            )
        assert (
            conn.execute(
                "SELECT intent_object_id FROM gov_missions WHERE record_id = ?", (rid,)
            ).fetchone()[0]
            == intent_alpha
        )
        return

    if case == "role_assignments_role":
        conn.execute(
            """
            INSERT OR IGNORE INTO gov_actors(
                actor_id, tenant_id, kind, display_name, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, 'human', 'A', 'm1.actor.v1', ?, ?)
            """,
            (ACTOR, alpha, STAMP, ACTOR),
        )
        alpha_role = generate_uuidv7()
        beta_role = generate_uuidv7()
        _register_object(conn, tenant_id=alpha, object_id=alpha_role, object_type="RoleProfile")
        _register_object(conn, tenant_id=beta, object_id=beta_role, object_type="RoleProfile")
        for role, tenant in ((alpha_role, alpha), (beta_role, beta)):
            conn.execute(
                """
                INSERT INTO gov_role_profiles(
                    role_object_id, revision, tenant_id, name, permissions_json,
                    jurisdiction_json, schema_version, created_at, created_by_actor_id
                ) VALUES (?, 1, ?, 'r', '["*"]', '{}', 'm1.role_profile.v1', ?, ?)
                """,
                (role, tenant, STAMP, ACTOR),
            )
        aid = generate_uuidv7()
        conn.execute(
            """
            INSERT INTO gov_role_assignments(
                assignment_id, tenant_id, actor_id, role_object_id, role_revision,
                workspace_object_id, jurisdiction_key, jurisdiction_value,
                effective_from, effective_until, created_at, created_by_actor_id,
                schema_version
            ) VALUES (?, ?, ?, ?, 1, ?, 'workspace', ?, ?, NULL, ?, ?, 'm1.role_assignment.v1')
            """,
            (
                aid,
                alpha,
                ACTOR,
                alpha_role,
                world["alpha_ws"],
                world["alpha_ws"],
                STAMP,
                STAMP,
                ACTOR,
            ),
        )
        before = count("gov_role_assignments")
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_role_assignments(
                    assignment_id, tenant_id, actor_id, role_object_id, role_revision,
                    workspace_object_id, jurisdiction_key, jurisdiction_value,
                    effective_from, effective_until, created_at, created_by_actor_id,
                    schema_version
                ) VALUES (?, ?, ?, ?, 1, ?, 'workspace', ?, ?, NULL, ?, ?, 'm1.role_assignment.v1')
                """,
                (
                    generate_uuidv7(),
                    alpha,
                    ACTOR,
                    beta_role,
                    world["alpha_ws"],
                    world["alpha_ws"],
                    STAMP,
                    STAMP,
                    ACTOR,
                ),
            )
        assert count("gov_role_assignments") == before
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                "UPDATE gov_role_assignments SET role_object_id = ? WHERE assignment_id = ?",
                (beta_role, aid),
            )
        assert (
            conn.execute(
                "SELECT role_object_id FROM gov_role_assignments WHERE assignment_id = ?",
                (aid,),
            ).fetchone()[0]
            == alpha_role
        )
        return

    if case == "events_subject":
        # Append-only: UPDATE blocked separately; INSERT cross-tenant must fail via v8.
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_domain_events(
                    event_id, tenant_id, ledger_sequence, event_type, payload_json,
                    correlation_id, causation_id, created_at, actor_id,
                    payload_schema_version, occurred_at, subject_object_id,
                    subject_revision, subject_refs_json
                ) VALUES (?, ?, 1, 'governance.command.accepted', '{}', ?, ?, ?, ?,
                          'm1.event.command_accepted.v1', ?, ?, 1, '{}')
                """,
                (
                    generate_uuidv7(),
                    alpha,
                    generate_uuidv7(),
                    generate_uuidv7(),
                    STAMP,
                    ACTOR,
                    STAMP,
                    world["beta_obj"],
                ),
            )
        eid = generate_uuidv7()
        conn.execute(
            """
            INSERT INTO gov_domain_events(
                event_id, tenant_id, ledger_sequence, event_type, payload_json,
                correlation_id, causation_id, created_at, actor_id,
                payload_schema_version, occurred_at, subject_object_id,
                subject_revision, subject_refs_json
            ) VALUES (?, ?, 1, 'governance.command.accepted', '{}', ?, ?, ?, ?,
                      'm1.event.command_accepted.v1', ?, ?, 1, '{}')
            """,
            (
                eid,
                alpha,
                generate_uuidv7(),
                generate_uuidv7(),
                STAMP,
                ACTOR,
                STAMP,
                world["alpha_obj"],
            ),
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only|cross-tenant"):
            conn.execute(
                "UPDATE gov_domain_events SET subject_object_id = ? WHERE event_id = ?",
                (world["beta_obj"], eid),
            )
        assert (
            conn.execute(
                "SELECT subject_object_id FROM gov_domain_events WHERE event_id = ?",
                (eid,),
            ).fetchone()[0]
            == world["alpha_obj"]
        )
        return

    if case == "evaluation_snapshots_subject":
        sid = generate_uuidv7()
        conn.execute(
            """
            INSERT INTO gov_evaluation_snapshots(
                snapshot_id, tenant_id, subject_object_id, subject_revision,
                input_refs_json, created_at
            ) VALUES (?, ?, ?, 1, '{}', ?)
            """,
            (sid, alpha, world["alpha_obj"], STAMP),
        )
        before = count("gov_evaluation_snapshots")
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_evaluation_snapshots(
                    snapshot_id, tenant_id, subject_object_id, subject_revision,
                    input_refs_json, created_at
                ) VALUES (?, ?, ?, 1, '{}', ?)
                """,
                (generate_uuidv7(), alpha, world["beta_obj"], STAMP),
            )
        assert count("gov_evaluation_snapshots") == before
        with pytest.raises(sqlite3.IntegrityError, match="append-only|cross-tenant"):
            conn.execute(
                "UPDATE gov_evaluation_snapshots SET subject_object_id = ? WHERE snapshot_id = ?",
                (world["beta_obj"], sid),
            )
        return

    if case == "transition_records_subject":
        tid = generate_uuidv7()
        conn.execute(
            """
            INSERT INTO gov_transition_records(
                transition_id, tenant_id, subject_object_id, from_state, to_state,
                definition_version, command_id, created_at
            ) VALUES (?, ?, ?, 'draft', 'ready', 'm1.task_lifecycle.v1', ?, ?)
            """,
            (tid, alpha, world["alpha_obj"], generate_uuidv7(), STAMP),
        )
        before = count("gov_transition_records")
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_transition_records(
                    transition_id, tenant_id, subject_object_id, from_state, to_state,
                    definition_version, command_id, created_at
                ) VALUES (?, ?, ?, 'draft', 'ready', 'm1.task_lifecycle.v1', ?, ?)
                """,
                (generate_uuidv7(), alpha, world["beta_obj"], generate_uuidv7(), STAMP),
            )
        assert count("gov_transition_records") == before
        with pytest.raises(sqlite3.IntegrityError, match="append-only|cross-tenant"):
            conn.execute(
                "UPDATE gov_transition_records SET subject_object_id = ? WHERE transition_id = ?",
                (world["beta_obj"], tid),
            )
        return

    if case == "command_subject_links_subject":
        conn.execute(
            """
            INSERT INTO gov_command_subject_links(
                command_id, tenant_id, subject_object_id, subject_revision,
                link_kind, linked_id
            ) VALUES (?, ?, ?, 1, 'decision', ?)
            """,
            (generate_uuidv7(), alpha, world["alpha_obj"], generate_uuidv7()),
        )
        before = count("gov_command_subject_links")
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_command_subject_links(
                    command_id, tenant_id, subject_object_id, subject_revision,
                    link_kind, linked_id
                ) VALUES (?, ?, ?, 1, 'decision', ?)
                """,
                (generate_uuidv7(), alpha, world["beta_obj"], generate_uuidv7()),
            )
        assert count("gov_command_subject_links") == before
        return

    if case == "test_plans_mission":
        plan_obj = generate_uuidv7()
        mission_alpha = generate_uuidv7()
        mission_beta = generate_uuidv7()
        for oid, tenant, kind in (
            (plan_obj, alpha, "TestPlan"),
            (mission_alpha, alpha, "Mission"),
            (mission_beta, beta, "Mission"),
        ):
            _register_object(conn, tenant_id=tenant, object_id=oid, object_type=kind)
        rid = generate_uuidv7()
        conn.execute(
            """
            INSERT INTO gov_test_plans(
                record_id, tenant_id, object_id, revision, mission_object_id,
                summary, content_hash, schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, 1, ?, 's', 'sha256:x', 'm1.test_plan.v1', ?, ?)
            """,
            (rid, alpha, plan_obj, mission_alpha, STAMP, ACTOR),
        )
        before = count("gov_test_plans")
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                """
                INSERT INTO gov_test_plans(
                    record_id, tenant_id, object_id, revision, mission_object_id,
                    summary, content_hash, schema_version, created_at, created_by_actor_id
                ) VALUES (?, ?, ?, 1, ?, 's', 'sha256:x', 'm1.test_plan.v1', ?, ?)
                """,
                (generate_uuidv7(), alpha, plan_obj, mission_beta, STAMP, ACTOR),
            )
        assert count("gov_test_plans") == before
        with pytest.raises(sqlite3.IntegrityError, match="cross-tenant"):
            conn.execute(
                "UPDATE gov_test_plans SET mission_object_id = ? WHERE record_id = ?",
                (mission_beta, rid),
            )
        return

    raise AssertionError(f"unknown case {case}")


def test_head_revision_consistency_requires_matching_revision_row() -> None:
    conn = _connect()
    world = _seed_two_tenants(conn)
    rev_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_object_revisions(
            revision_id, tenant_id, object_id, revision, supersedes_revision,
            content_hash, payload_json, finalized, schema_version,
            created_at, created_by_actor_id
        ) VALUES (?, ?, ?, 1, NULL, 'sha256:x', '{}', 1, 'm1.revision.v1', ?, ?)
        """,
        (rev_id, world["alpha"], world["alpha_obj"], STAMP, ACTOR),
    )
    with pytest.raises(sqlite3.IntegrityError, match="cross-tenant reference forbidden"):
        conn.execute(
            """
            INSERT INTO gov_object_heads(object_id, tenant_id, head_revision, head_revision_id)
            VALUES (?, ?, 2, ?)
            """,
            (world["alpha_obj"], world["alpha"], rev_id),
        )


def test_v8_upgrade_function_is_idempotent() -> None:
    conn = _connect()
    migrate_governance(conn)
    upgrade_tenant_coupled_ownership(conn)
    upgrade_tenant_coupled_ownership(conn)
    assert governance_schema_version(conn) == 16
