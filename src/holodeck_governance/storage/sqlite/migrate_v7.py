"""Migration 7: enforcement columns, append-only triggers, tenant-coupled refs."""

from __future__ import annotations

import sqlite3


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, ddl_type: str
) -> None:
    cols = {
        str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def upgrade_enforcement_and_envelopes(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "gov_objects"):
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS gov_objects_tenant_object "
            "ON gov_objects(tenant_id, object_id)"
        )

    if _table_exists(conn, "gov_evaluation_results"):
        _add_column_if_missing(
            conn, "gov_evaluation_results", "primitive_results_json", "TEXT"
        )
        _add_column_if_missing(
            conn, "gov_evaluation_results", "policy_binding_id", "TEXT"
        )
        _add_column_if_missing(
            conn,
            "gov_evaluation_results",
            "evaluator_implementation_id",
            "TEXT",
        )
        _add_column_if_missing(
            conn, "gov_evaluation_results", "selected_authority_json", "TEXT"
        )

    if _table_exists(conn, "gov_evaluation_snapshots"):
        _add_column_if_missing(
            conn, "gov_evaluation_snapshots", "policy_binding_id", "TEXT"
        )
        _add_column_if_missing(
            conn, "gov_evaluation_snapshots", "authority_selection_json", "TEXT"
        )

    if _table_exists(conn, "gov_domain_events"):
        _add_column_if_missing(conn, "gov_domain_events", "actor_id", "TEXT")
        _add_column_if_missing(
            conn, "gov_domain_events", "payload_schema_version", "TEXT"
        )
        _add_column_if_missing(conn, "gov_domain_events", "occurred_at", "TEXT")
        _add_column_if_missing(
            conn, "gov_domain_events", "subject_object_id", "TEXT"
        )
        _add_column_if_missing(
            conn, "gov_domain_events", "subject_revision", "INTEGER"
        )
        _add_column_if_missing(
            conn, "gov_domain_events", "subject_refs_json", "TEXT"
        )

    # Finalized revision immutability
    conn.execute("DROP TRIGGER IF EXISTS gov_revisions_block_update_finalized")
    conn.execute(
        """
        CREATE TRIGGER gov_revisions_block_update_finalized
        BEFORE UPDATE ON gov_object_revisions
        WHEN OLD.finalized = 1
        BEGIN
            SELECT RAISE(ABORT, 'finalized revision is immutable');
        END
        """
    )
    conn.execute("DROP TRIGGER IF EXISTS gov_revisions_block_delete_finalized")
    conn.execute(
        """
        CREATE TRIGGER gov_revisions_block_delete_finalized
        BEFORE DELETE ON gov_object_revisions
        WHEN OLD.finalized = 1
        BEGIN
            SELECT RAISE(ABORT, 'finalized revision is immutable');
        END
        """
    )

    # Append-only ledger / evaluation / receipt tables
    for table in (
        "gov_domain_events",
        "gov_evaluation_snapshots",
        "gov_evaluation_results",
        "gov_command_receipts",
        "gov_transition_records",
        "gov_outbox_attempts",
    ):
        if not _table_exists(conn, table):
            continue
        conn.execute(f"DROP TRIGGER IF EXISTS {table}_block_update")
        conn.execute(
            f"""
            CREATE TRIGGER {table}_block_update
            BEFORE UPDATE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only');
            END
            """
        )
        conn.execute(f"DROP TRIGGER IF EXISTS {table}_block_delete")
        conn.execute(
            f"""
            CREATE TRIGGER {table}_block_delete
            BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only');
            END
            """
        )

    # Tenant-coupled reference checks for typed object FKs.
    # nullable_cols may be NULL; non-null columns always checked.
    ref_checks: list[tuple[str, str, bool]] = [
        ("gov_sources", "workspace_object_id", False),
        ("gov_intents", "workspace_object_id", False),
        ("gov_missions", "workspace_object_id", False),
        ("gov_tasks", "workspace_object_id", False),
        ("gov_tasks", "mission_object_id", False),
        ("gov_runs", "task_object_id", False),
        ("gov_runs", "mission_object_id", True),
        ("gov_requirements", "mission_object_id", False),
        ("gov_test_plans", "requirement_object_id", False),
        ("gov_evidence", "requirement_object_id", False),
        ("gov_evidence", "artifact_object_id", False),
        ("gov_approvals", "subject_object_id", False),
        ("gov_reviews", "subject_object_id", False),
        ("gov_decisions", "subject_object_id", False),
        ("gov_escalations", "subject_object_id", False),
        ("gov_delegated_grants", "subject_object_id", False),
        ("gov_external_references", "subject_object_id", True),
        ("gov_traceability_edges", "from_object_id", False),
        ("gov_traceability_edges", "to_object_id", False),
    ]
    for table, column, nullable in ref_checks:
        if not _table_exists(conn, table):
            continue
        cols = {
            str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in cols:
            continue
        null_guard = f"NEW.{column} IS NOT NULL AND " if nullable else ""
        trigger = f"{table}_tenant_{column}_ins"
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        conn.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE INSERT ON {table}
            WHEN {null_guard}NOT EXISTS (
                SELECT 1 FROM gov_objects o
                WHERE o.object_id = NEW.{column} AND o.tenant_id = NEW.tenant_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'cross-tenant reference forbidden: {table}.{column}');
            END
            """
        )
        trigger_u = f"{table}_tenant_{column}_upd"
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger_u}")
        conn.execute(
            f"""
            CREATE TRIGGER {trigger_u}
            BEFORE UPDATE OF {column}, tenant_id ON {table}
            WHEN {null_guard}NOT EXISTS (
                SELECT 1 FROM gov_objects o
                WHERE o.object_id = NEW.{column} AND o.tenant_id = NEW.tenant_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'cross-tenant reference forbidden: {table}.{column}');
            END
            """
        )
