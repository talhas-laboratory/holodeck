"""Migration 13: tenant-coupled references for collaboration tables."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v8 import install_tenant_object_triggers
from holodeck_governance.storage.sqlite.migrate_v9 import install_tenant_actor_triggers


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


def install_tenant_row_ref_triggers(
    conn: sqlite3.Connection,
    *,
    table: str,
    column: str,
    ref_table: str,
    ref_pk: str,
    nullable: bool = False,
    trigger_prefix: str | None = None,
) -> None:
    """Require NEW.tenant_id to match the referenced row's tenant_id."""

    if not _table_exists(conn, table) or not _table_exists(conn, ref_table):
        return
    cols = _columns(conn, table)
    if column not in cols or "tenant_id" not in cols:
        return
    prefix = trigger_prefix or f"{table}_tenant_{column}"
    null_guard = f"NEW.{column} IS NOT NULL AND " if nullable else ""
    for kind, when_extra in (
        ("ins", f"BEFORE INSERT ON {table}"),
        ("upd", f"BEFORE UPDATE OF {column}, tenant_id ON {table}"),
    ):
        name = f"{prefix}_{kind}"
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            {when_extra}
            WHEN {null_guard}NOT EXISTS (
                SELECT 1 FROM {ref_table} r
                WHERE r.{ref_pk} = NEW.{column}
                  AND r.tenant_id = NEW.tenant_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'cross-tenant reference forbidden: {table}.{column}'
                );
            END
            """
        )


def upgrade_collaboration_tenant_coupling(conn: sqlite3.Connection) -> None:
    install_tenant_actor_triggers(
        conn, table="gov_collaboration_endpoints", column="created_by_actor_id"
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_external_actor_mappings",
        column="endpoint_id",
        ref_table="gov_collaboration_endpoints",
        ref_pk="endpoint_id",
    )
    install_tenant_actor_triggers(
        conn, table="gov_external_actor_mappings", column="actor_id"
    )
    install_tenant_actor_triggers(
        conn, table="gov_external_actor_mappings", column="created_by_actor_id"
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_external_actor_mappings",
        column="external_identity_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_inbound_event_receipts",
        column="signed_source_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_inbound_event_receipts",
        column="endpoint_id",
        ref_table="gov_collaboration_endpoints",
        ref_pk="endpoint_id",
        nullable=True,
    )
    install_tenant_object_triggers(
        conn, table="gov_task_origins", column="object_id"
    )
    install_tenant_actor_triggers(conn, table="gov_task_origins", column="actor_id")
    install_tenant_actor_triggers(
        conn, table="gov_task_origins", column="created_by_actor_id"
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_task_origins",
        column="inbound_receipt_id",
        ref_table="gov_inbound_event_receipts",
        ref_pk="receipt_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_task_origins",
        column="source_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_task_origins",
        column="location_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_task_origins",
        column="parent_location_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
        nullable=True,
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_task_origins",
        column="endpoint_id",
        ref_table="gov_collaboration_endpoints",
        ref_pk="endpoint_id",
        nullable=True,
    )
