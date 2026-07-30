"""Migration 8: tenant-coupled ownership for row identity and omitted refs.

Does not modify v7. Safe to apply on databases that already have v7.
"""

from __future__ import annotations

import sqlite3


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {
        str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def install_tenant_object_triggers(
    conn: sqlite3.Connection,
    *,
    table: str,
    column: str,
    nullable: bool = False,
    trigger_prefix: str | None = None,
) -> None:
    """Install BEFORE INSERT/UPDATE triggers that couple tenant_id to object ownership."""

    if not _table_exists(conn, table):
        return
    cols = _columns(conn, table)
    if column not in cols or "tenant_id" not in cols:
        return
    prefix = trigger_prefix or f"{table}_tenant_{column}"
    null_guard = f"NEW.{column} IS NOT NULL AND " if nullable else ""
    for kind, when_extra in (
        ("ins", f"BEFORE INSERT ON {table}"),
        (
            "upd",
            f"BEFORE UPDATE OF {column}, tenant_id ON {table}",
        ),
    ):
        name = f"{prefix}_{kind}"
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            {when_extra}
            WHEN {null_guard}NOT EXISTS (
                SELECT 1 FROM gov_objects o
                WHERE o.object_id = NEW.{column}
                  AND o.tenant_id = NEW.tenant_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'cross-tenant reference forbidden: {table}.{column}'
                );
            END
            """
        )


def upgrade_tenant_coupled_ownership(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "gov_objects"):
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS gov_objects_tenant_object "
            "ON gov_objects(tenant_id, object_id)"
        )

    # Own governed identity: row.tenant_id must own row's identity object.
    own_identity: list[tuple[str, str]] = [
        ("gov_object_revisions", "object_id"),
        ("gov_object_heads", "object_id"),
        ("gov_workspaces", "object_id"),
        ("gov_sources", "object_id"),
        ("gov_intents", "object_id"),
        ("gov_missions", "object_id"),
        ("gov_tasks", "object_id"),
        ("gov_requirements", "object_id"),
        ("gov_test_plans", "object_id"),
        ("gov_runs", "object_id"),
        ("gov_artifacts", "object_id"),
        ("gov_evidence", "object_id"),
        ("gov_reviews", "object_id"),
        ("gov_approvals", "object_id"),
        ("gov_decisions", "object_id"),
        ("gov_escalations", "object_id"),
        ("gov_role_profiles", "role_object_id"),
    ]
    for table, column in own_identity:
        install_tenant_object_triggers(conn, table=table, column=column)

    # Relationship refs omitted from v7 (plus remaining subject refs).
    relationship_refs: list[tuple[str, str, bool]] = [
        ("gov_missions", "intent_object_id", False),
        ("gov_test_plans", "mission_object_id", False),
        ("gov_role_assignments", "role_object_id", False),
        ("gov_role_assignments", "workspace_object_id", True),
        ("gov_evaluation_snapshots", "subject_object_id", False),
        ("gov_transition_records", "subject_object_id", False),
        ("gov_command_subject_links", "subject_object_id", False),
        ("gov_domain_events", "subject_object_id", True),
    ]
    for table, column, nullable in relationship_refs:
        install_tenant_object_triggers(
            conn, table=table, column=column, nullable=nullable
        )

    # Compound head consistency: revision row must match tenant, object, and number.
    if _table_exists(conn, "gov_object_heads") and _table_exists(
        conn, "gov_object_revisions"
    ):
        for kind, when_extra in (
            ("ins", "BEFORE INSERT ON gov_object_heads"),
            (
                "upd",
                "BEFORE UPDATE OF head_revision_id, head_revision, object_id, tenant_id "
                "ON gov_object_heads",
            ),
        ):
            name = f"gov_object_heads_revision_consistency_{kind}"
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
            conn.execute(
                f"""
                CREATE TRIGGER {name}
                {when_extra}
                WHEN NOT EXISTS (
                    SELECT 1 FROM gov_object_revisions r
                    WHERE r.revision_id = NEW.head_revision_id
                      AND r.tenant_id = NEW.tenant_id
                      AND r.object_id = NEW.object_id
                      AND r.revision = NEW.head_revision
                )
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'cross-tenant reference forbidden: gov_object_heads.head_revision'
                    );
                END
                """
            )
