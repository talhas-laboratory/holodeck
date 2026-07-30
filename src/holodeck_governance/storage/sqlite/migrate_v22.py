"""Migration 22: typed readiness on decisions + observation coupling."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v8 import install_tenant_object_triggers
from holodeck_governance.storage.sqlite.migrate_v9 import install_tenant_actor_triggers
from holodeck_governance.storage.sqlite.migrate_v13 import install_tenant_row_ref_triggers


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


def _install_observation_source_coupling(conn: sqlite3.Connection) -> None:
    """Require observation tenant/workspace to match the referenced source."""

    if not _table_exists(conn, "gov_workspace_source_observations"):
        return
    if not _table_exists(conn, "gov_workspace_sources"):
        return
    for kind, when_extra in (
        ("ins", "BEFORE INSERT ON gov_workspace_source_observations"),
        (
            "upd",
            "BEFORE UPDATE OF source_id, tenant_id, workspace_object_id "
            "ON gov_workspace_source_observations",
        ),
    ):
        name = f"gov_workspace_source_observations_source_coupling_{kind}"
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            {when_extra}
            WHEN NOT EXISTS (
                SELECT 1 FROM gov_workspace_sources s
                WHERE s.source_id = NEW.source_id
                  AND s.tenant_id = NEW.tenant_id
                  AND s.workspace_object_id = NEW.workspace_object_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'observation tenant/workspace must match source'
                );
            END
            """
        )


def upgrade_readiness_auth_and_observation_coupling(conn: sqlite3.Connection) -> None:
    """Add authorized_readiness_level, observation_ids_json, and observation coupling."""

    if "authorized_readiness_level" not in _columns(conn, "gov_workspace_decisions"):
        conn.execute(
            """
            ALTER TABLE gov_workspace_decisions
            ADD COLUMN authorized_readiness_level TEXT
            """
        )

    if "observation_ids_json" not in _columns(conn, "gov_context_modules"):
        conn.execute(
            """
            ALTER TABLE gov_context_modules
            ADD COLUMN observation_ids_json TEXT NOT NULL DEFAULT '[]'
            """
        )

    if _table_exists(conn, "gov_workspace_source_observations"):
        install_tenant_object_triggers(
            conn,
            table="gov_workspace_source_observations",
            column="workspace_object_id",
        )
        install_tenant_actor_triggers(
            conn,
            table="gov_workspace_source_observations",
            column="created_by_actor_id",
        )
        install_tenant_row_ref_triggers(
            conn,
            table="gov_workspace_source_observations",
            column="source_id",
            ref_table="gov_workspace_sources",
            ref_pk="source_id",
        )
        _install_observation_source_coupling(conn)
