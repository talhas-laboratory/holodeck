"""Migration 9: tenant-coupled authority references.

Does not modify v8. Safe to apply on databases that already have v8.
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


def install_tenant_actor_triggers(
    conn: sqlite3.Connection,
    *,
    table: str,
    column: str,
    trigger_prefix: str | None = None,
) -> None:
    """Require NEW.tenant_id to match gov_actors.tenant_id for the referenced actor."""

    if not _table_exists(conn, table) or not _table_exists(conn, "gov_actors"):
        return
    cols = _columns(conn, table)
    if column not in cols or "tenant_id" not in cols:
        return
    prefix = trigger_prefix or f"{table}_tenant_{column}"
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
            WHEN NOT EXISTS (
                SELECT 1 FROM gov_actors a
                WHERE a.actor_id = NEW.{column}
                  AND a.tenant_id = NEW.tenant_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'cross-tenant authority reference forbidden: {table}.{column}'
                );
            END
            """
        )


def install_revocation_grant_tenant_triggers(conn: sqlite3.Connection) -> None:
    """Require revocation.tenant_id to match the referenced grant's tenant."""

    table = "gov_revocation_decisions"
    if not _table_exists(conn, table) or not _table_exists(conn, "gov_delegated_grants"):
        return
    cols = _columns(conn, table)
    if "grant_id" not in cols or "tenant_id" not in cols:
        return
    for kind, when_extra in (
        ("ins", f"BEFORE INSERT ON {table}"),
        ("upd", f"BEFORE UPDATE OF grant_id, tenant_id ON {table}"),
    ):
        name = f"{table}_tenant_grant_id_{kind}"
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            {when_extra}
            WHEN NOT EXISTS (
                SELECT 1 FROM gov_delegated_grants g
                WHERE g.grant_id = NEW.grant_id
                  AND g.tenant_id = NEW.tenant_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'cross-tenant authority reference forbidden: {table}.grant_id'
                );
            END
            """
        )


def upgrade_tenant_coupled_authority(conn: sqlite3.Connection) -> None:
    install_revocation_grant_tenant_triggers(conn)
    install_tenant_actor_triggers(
        conn, table="gov_role_assignments", column="actor_id"
    )
    install_tenant_actor_triggers(
        conn, table="gov_delegated_grants", column="delegator_actor_id"
    )
    install_tenant_actor_triggers(
        conn, table="gov_delegated_grants", column="recipient_actor_id"
    )
