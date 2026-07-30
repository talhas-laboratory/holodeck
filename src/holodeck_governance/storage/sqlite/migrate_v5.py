"""Migration 5: command path, authority, remaining records, constrained edges."""

from __future__ import annotations

import sqlite3


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _stash_legacy_table(conn: sqlite3.Connection, table: str) -> None:
    if not _table_exists(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} RENAME TO {table}_pre_v5")


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    if not _table_exists(conn, table):
        return []
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _copy_common_columns(
    conn: sqlite3.Connection, source: str, destination: str
) -> None:
    if not _table_exists(conn, source):
        return
    shared = [
        col for col in _columns(conn, destination) if col in set(_columns(conn, source))
    ]
    if not shared:
        return
    cols = ", ".join(shared)
    conn.execute(
        f"INSERT OR IGNORE INTO {destination} ({cols}) SELECT {cols} FROM {source}"
    )


def _copy_transition_rows(conn: sqlite3.Connection) -> None:
    source = "gov_transition_records_pre_v5"
    if not _table_exists(conn, source):
        return
    src_cols = set(_columns(conn, source))
    # New schema requires command_id; synthesize a stable placeholder when absent.
    if "command_id" in src_cols:
        _copy_common_columns(conn, source, "gov_transition_records")
        return
    shared = [
        col
        for col in _columns(conn, "gov_transition_records")
        if col in src_cols and col != "command_id"
    ]
    if not shared:
        return
    cols = ", ".join(shared)
    conn.execute(
        f"""
        INSERT OR IGNORE INTO gov_transition_records ({cols}, command_id)
        SELECT {cols}, 'legacy-pre-v5-' || transition_id
        FROM {source}
        """
    )


def upgrade_command_path_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_actors (
            actor_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            kind TEXT NOT NULL,
            display_name TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_role_profiles (
            role_object_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            name TEXT NOT NULL,
            permissions_json TEXT NOT NULL,
            jurisdiction_json TEXT NOT NULL DEFAULT '{}',
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            PRIMARY KEY (role_object_id, revision),
            FOREIGN KEY (role_object_id) REFERENCES gov_objects(object_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_role_assignments (
            assignment_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            actor_id TEXT NOT NULL REFERENCES gov_actors(actor_id),
            role_object_id TEXT NOT NULL,
            role_revision INTEGER NOT NULL,
            workspace_object_id TEXT,
            jurisdiction_key TEXT NOT NULL,
            jurisdiction_value TEXT NOT NULL,
            effective_from TEXT NOT NULL,
            effective_until TEXT,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            FOREIGN KEY (role_object_id, role_revision)
                REFERENCES gov_role_profiles(role_object_id, revision)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_revocation_decisions (
            revocation_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            grant_id TEXT NOT NULL REFERENCES gov_delegated_grants(grant_id),
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            rationale TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )

    legacy_command_tables = (
        "gov_outbox_attempts",
        "gov_outbox_items",
        "gov_transition_records",
        "gov_domain_events",
        "gov_evaluation_results",
        "gov_evaluation_snapshots",
        "gov_command_receipts",
    )
    for table in legacy_command_tables:
        _stash_legacy_table(conn, table)

    conn.execute(
        """
        CREATE TABLE gov_command_receipts (
            receipt_id TEXT PRIMARY KEY,
            command_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            idempotency_key TEXT NOT NULL,
            semantic_hash TEXT NOT NULL,
            outcome TEXT NOT NULL,
            reason_codes_json TEXT NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL,
            evaluation_result_id TEXT,
            UNIQUE(tenant_id, idempotency_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_evaluation_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            subject_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            subject_revision INTEGER NOT NULL,
            input_refs_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_evaluation_results (
            result_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            snapshot_id TEXT NOT NULL REFERENCES gov_evaluation_snapshots(snapshot_id),
            evaluator_contract_version TEXT NOT NULL,
            outcome TEXT NOT NULL,
            reason_codes_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_domain_events (
            event_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            ledger_sequence INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            causation_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(tenant_id, ledger_sequence)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_transition_records (
            transition_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            subject_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            from_state TEXT NOT NULL,
            to_state TEXT NOT NULL,
            definition_version TEXT NOT NULL,
            command_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_outbox_items (
            outbox_item_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            domain_event_id TEXT NOT NULL REFERENCES gov_domain_events(event_id),
            delivery_purpose TEXT NOT NULL,
            dedup_key TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            lease_owner TEXT,
            lease_until TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TEXT,
            UNIQUE(tenant_id, dedup_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_outbox_attempts (
            attempt_id TEXT PRIMARY KEY,
            outbox_item_id TEXT NOT NULL REFERENCES gov_outbox_items(outbox_item_id),
            attempt_number INTEGER NOT NULL,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # Preserve prior lazy-schema rows into the numbered-migration tables.
    _copy_common_columns(conn, "gov_command_receipts_pre_v5", "gov_command_receipts")
    _copy_common_columns(
        conn, "gov_evaluation_snapshots_pre_v5", "gov_evaluation_snapshots"
    )
    _copy_common_columns(
        conn, "gov_evaluation_results_pre_v5", "gov_evaluation_results"
    )
    _copy_common_columns(conn, "gov_domain_events_pre_v5", "gov_domain_events")
    _copy_transition_rows(conn)
    _copy_common_columns(conn, "gov_outbox_items_pre_v5", "gov_outbox_items")
    _copy_common_columns(conn, "gov_outbox_attempts_pre_v5", "gov_outbox_attempts")
    for table in legacy_command_tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}_pre_v5")

    for ddl in (
        """
        CREATE TABLE gov_requirements (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            mission_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            statement TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_test_plans (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            mission_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            summary TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_runs (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            task_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            mission_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            state TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_artifacts (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            kind TEXT NOT NULL,
            locator TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_evidence (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            requirement_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            artifact_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_reviews (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            subject_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            subject_revision INTEGER NOT NULL,
            status TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_approvals (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            subject_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            subject_revision INTEGER NOT NULL,
            decision TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_decisions (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            subject_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            subject_revision INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            command_id TEXT,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_escalations (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            subject_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            trigger TEXT NOT NULL,
            outbox_item_id TEXT,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """,
        """
        CREATE TABLE gov_command_subject_links (
            command_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            subject_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            subject_revision INTEGER NOT NULL,
            link_kind TEXT NOT NULL,
            linked_id TEXT NOT NULL,
            PRIMARY KEY (command_id, link_kind, linked_id)
        )
        """,
    ):
        conn.execute(ddl)

    conn.execute(
        """
        CREATE TABLE gov_traceability_edges_v5 (
            edge_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            edge_type TEXT NOT NULL,
            from_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            from_revision INTEGER NOT NULL CHECK (from_revision >= 1),
            to_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            to_revision INTEGER NOT NULL CHECK (to_revision >= 1),
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            provenance_ref TEXT,
            validity_status TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            FOREIGN KEY (from_object_id, from_revision)
                REFERENCES gov_object_revisions(object_id, revision),
            FOREIGN KEY (to_object_id, to_revision)
                REFERENCES gov_object_revisions(object_id, revision)
        )
        """
    )
    try:
        conn.execute(
            """
            INSERT INTO gov_traceability_edges_v5
            SELECT edge_id, tenant_id, edge_type, from_object_id, from_revision,
                   to_object_id, to_revision, created_at, created_by_actor_id,
                   provenance_ref, validity_status, schema_version
            FROM gov_traceability_edges
            """
        )
    except sqlite3.Error as exc:
        # Fail closed: never DROP the live edge table after a failed copy.
        conn.execute("DROP TABLE IF EXISTS gov_traceability_edges_v5")
        raise RuntimeError(
            "migrate_v5 edge upgrade failed; preserving existing gov_traceability_edges"
        ) from exc
    conn.execute("DROP TABLE IF EXISTS gov_traceability_edges")
    conn.execute("ALTER TABLE gov_traceability_edges_v5 RENAME TO gov_traceability_edges")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS gov_edges_tenant ON gov_traceability_edges(tenant_id, created_at)"
    )

    cols = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(gov_tasks)").fetchall()
    }
    if "supersedes_revision" not in cols:
        conn.execute("ALTER TABLE gov_tasks ADD COLUMN supersedes_revision INTEGER")
