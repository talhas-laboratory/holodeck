"""Migration 14: exact actor-mapping attribution on accepted intake."""

from __future__ import annotations

import sqlite3

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


def _add_column_if_missing(
    conn: sqlite3.Connection, *, table: str, column: str, ddl: str
) -> None:
    if column in _columns(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def upgrade_accepted_intake_mapping_attribution(conn: sqlite3.Connection) -> None:
    """Persist the verified mapping used for accepted intake attribution."""

    _add_column_if_missing(
        conn,
        table="gov_inbound_event_receipts",
        column="mapping_id",
        ddl="mapping_id TEXT REFERENCES gov_external_actor_mappings(mapping_id)",
    )
    _add_column_if_missing(
        conn,
        table="gov_inbound_event_receipts",
        column="external_actor_id",
        ddl="external_actor_id TEXT",
    )
    _add_column_if_missing(
        conn,
        table="gov_task_origins",
        column="mapping_id",
        ddl="mapping_id TEXT REFERENCES gov_external_actor_mappings(mapping_id)",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_inbound_event_receipts",
        column="mapping_id",
        ref_table="gov_external_actor_mappings",
        ref_pk="mapping_id",
        nullable=True,
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_task_origins",
        column="mapping_id",
        ref_table="gov_external_actor_mappings",
        ref_pk="mapping_id",
        nullable=True,
    )
