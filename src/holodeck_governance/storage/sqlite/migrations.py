"""Additive governance schema migrations (separate version space from M0)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from holodeck_governance.storage.sqlite.migrate_v5 import upgrade_command_path_tables
from holodeck_governance.storage.sqlite.migrate_v6 import upgrade_record_family_alignment
from holodeck_governance.storage.sqlite.migrate_v7 import upgrade_enforcement_and_envelopes
from holodeck_governance.storage.sqlite.migrate_v8 import upgrade_tenant_coupled_ownership
from holodeck_governance.storage.sqlite.migrate_v9 import upgrade_tenant_coupled_authority
from holodeck_governance.storage.sqlite.migrate_v10 import upgrade_authority_issuance_basis
from holodeck_governance.storage.sqlite.migrate_v11 import (
    upgrade_collaboration_bindings_and_receipts,
)
from holodeck_governance.storage.sqlite.migrate_v12 import upgrade_task_origins
from holodeck_governance.storage.sqlite.migrate_v13 import (
    upgrade_collaboration_tenant_coupling,
)
from holodeck_governance.storage.sqlite.migrate_v14 import (
    upgrade_accepted_intake_mapping_attribution,
)
from holodeck_governance.storage.sqlite.migrate_v15 import (
    upgrade_outbound_collaboration_messages,
)
from holodeck_governance.storage.sqlite.migrate_v16 import upgrade_workspace_bindings
from holodeck_governance.storage.sqlite.migrate_v17 import (
    upgrade_workspace_genesis_proposals,
)
from holodeck_governance.storage.sqlite.migrate_v18 import (
    upgrade_workspace_binding_active_uniques,
)
from holodeck_governance.storage.sqlite.migrate_v19 import (
    WORKSPACE_INTELLIGENCE_TABLES,
    upgrade_workspace_intelligence,
)

Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]


def migration_now() -> str:
    return datetime.now(UTC).isoformat()


def migrate_governance(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gov_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {
        int(row[0])
        for row in conn.execute(
            "SELECT version FROM gov_schema_migrations ORDER BY version"
        ).fetchall()
    }
    for version, _name, upgrade in GOVERNANCE_MIGRATIONS:
        if version in applied:
            continue
        previous = conn.isolation_level
        conn.isolation_level = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            upgrade(conn)
            conn.execute(
                "INSERT INTO gov_schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, migration_now()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.isolation_level = previous


def _upgrade_tenants(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_tenants (
            tenant_id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            provenance_ref TEXT,
            status TEXT NOT NULL,
            is_default_local INTEGER NOT NULL CHECK (is_default_local IN (0, 1)),
            CHECK (tenant_id = tenant_id)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX gov_tenants_one_default
        ON gov_tenants(is_default_local)
        WHERE is_default_local = 1
        """
    )


def _upgrade_objects_and_revisions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_objects (
            object_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_type TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_object_revisions (
            revision_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL CHECK (revision >= 1),
            supersedes_revision INTEGER,
            content_hash TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            finalized INTEGER NOT NULL CHECK (finalized IN (0, 1)),
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE (object_id, revision),
            CHECK (
                supersedes_revision IS NULL
                OR supersedes_revision < revision
            )
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_object_heads (
            object_id TEXT PRIMARY KEY REFERENCES gov_objects(object_id),
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            head_revision INTEGER NOT NULL CHECK (head_revision >= 1),
            head_revision_id TEXT NOT NULL REFERENCES gov_object_revisions(revision_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX gov_object_revisions_object ON gov_object_revisions(object_id, revision)"
    )


def _upgrade_work_vocabulary(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_workspaces (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_sources (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            kind TEXT NOT NULL,
            locator TEXT NOT NULL,
            provenance_ref TEXT,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_intents (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            statement TEXT NOT NULL,
            constraints_json TEXT NOT NULL,
            non_goals_json TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_missions (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            intent_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            summary TEXT NOT NULL,
            status TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_tasks (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            mission_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            title TEXT NOT NULL,
            state TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """
    )


def _upgrade_authority_and_graph(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_traceability_edges (
            edge_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            edge_type TEXT NOT NULL,
            from_object_id TEXT NOT NULL,
            from_revision INTEGER NOT NULL CHECK (from_revision >= 1),
            to_object_id TEXT NOT NULL,
            to_revision INTEGER NOT NULL CHECK (to_revision >= 1),
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            provenance_ref TEXT,
            validity_status TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_external_references (
            reference_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            provider TEXT NOT NULL,
            object_type TEXT NOT NULL,
            external_object_id TEXT NOT NULL,
            locator TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            subject_object_id TEXT,
            content_hash TEXT,
            schema_version TEXT NOT NULL,
            UNIQUE(tenant_id, provider, object_type, external_object_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_policy_bindings (
            binding_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            scope TEXT NOT NULL,
            evaluator_id TEXT NOT NULL,
            parameters_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            precedence INTEGER NOT NULL CHECK (precedence >= 1),
            effective_from TEXT NOT NULL,
            effective_until TEXT,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_delegated_grants (
            grant_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            delegator_actor_id TEXT NOT NULL,
            recipient_actor_id TEXT NOT NULL,
            permission TEXT NOT NULL,
            subject_object_id TEXT NOT NULL,
            subject_revision INTEGER NOT NULL CHECK (subject_revision >= 1),
            effective_from TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            redelegatable INTEGER NOT NULL CHECK (redelegatable IN (0, 1)),
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX gov_edges_tenant ON gov_traceability_edges(tenant_id, created_at)"
    )
    conn.execute(
        "CREATE INDEX gov_grants_tenant_subject ON gov_delegated_grants(tenant_id, subject_object_id)"
    )


GOVERNANCE_MIGRATIONS: list[Migration] = [
    (1, "tenants", _upgrade_tenants),
    (2, "objects_and_revisions", _upgrade_objects_and_revisions),
    (3, "work_vocabulary", _upgrade_work_vocabulary),
    (4, "authority_and_graph", _upgrade_authority_and_graph),
    (5, "command_path_and_records", upgrade_command_path_tables),
    (6, "record_family_alignment", upgrade_record_family_alignment),
    (7, "enforcement_envelopes_triggers", upgrade_enforcement_and_envelopes),
    (8, "tenant_coupled_ownership", upgrade_tenant_coupled_ownership),
    (9, "tenant_coupled_authority", upgrade_tenant_coupled_authority),
    (10, "authority_issuance_basis", upgrade_authority_issuance_basis),
    (11, "collaboration_bindings_and_receipts", upgrade_collaboration_bindings_and_receipts),
    (12, "task_origins", upgrade_task_origins),
    (13, "collaboration_tenant_coupling", upgrade_collaboration_tenant_coupling),
    (14, "accepted_intake_mapping_attribution", upgrade_accepted_intake_mapping_attribution),
    (15, "outbound_collaboration_messages", upgrade_outbound_collaboration_messages),
    (16, "workspace_bindings", upgrade_workspace_bindings),
    (17, "workspace_genesis_proposals", upgrade_workspace_genesis_proposals),
    (18, "workspace_binding_active_uniques", upgrade_workspace_binding_active_uniques),
    (19, "workspace_intelligence", upgrade_workspace_intelligence),
]


def governance_schema_version(conn: sqlite3.Connection) -> int:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gov_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM gov_schema_migrations").fetchone()
    return int(row[0])


def rollback_governance_migration(conn: sqlite3.Connection, version: int) -> None:
    """Drop objects introduced by a single governance migration version.

    Additive M1 rollback is explicit and version-scoped. It does not rewrite M0 tables.
    """

    if version == 19:
        for table in WORKSPACE_INTELLIGENCE_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 18:
        for table in (
            "gov_collaboration_location_bindings",
            "gov_repository_bindings",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        from holodeck_governance.storage.sqlite.migrate_v16 import (
            upgrade_workspace_bindings as rebuild_v16_bindings,
        )

        rebuild_v16_bindings(conn)
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 17:
        conn.execute("DROP TABLE IF EXISTS gov_workspace_genesis_proposals")
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 16:
        for table in (
            "gov_collaboration_location_bindings",
            "gov_repository_bindings",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 15:
        conn.execute("DROP TABLE IF EXISTS gov_outbound_collaboration_messages")
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 14:
        # Column + trigger migration; rolling back removes the version marker only.
        # SQLite cannot DROP COLUMN portably here without table rebuild.
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 13:
        # Trigger-only migration; rolling back removes the version marker.
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 12:
        conn.execute("DROP TABLE IF EXISTS gov_task_origins")
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 11:
        for table in (
            "gov_inbound_event_receipts",
            "gov_external_actor_mappings",
            "gov_collaboration_endpoints",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 10:
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 9:
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 8:
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 7:
        # Trigger/column alignment; rolling back removes the version marker only.
        # Triggers remain until explicitly dropped by a forward repair.
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 6:
        # Alignment-only migration; rolling back removes the version marker.
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 5:
        for table in (
            "gov_command_subject_links",
            "gov_escalations",
            "gov_decisions",
            "gov_approvals",
            "gov_reviews",
            "gov_evidence",
            "gov_artifacts",
            "gov_runs",
            "gov_test_plans",
            "gov_requirements",
            "gov_outbox_attempts",
            "gov_outbox_items",
            "gov_transition_records",
            "gov_domain_events",
            "gov_evaluation_results",
            "gov_evaluation_snapshots",
            "gov_command_receipts",
            "gov_revocation_decisions",
            "gov_role_assignments",
            "gov_role_profiles",
            "gov_actors",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    if version == 4:
        for table in (
            "gov_delegated_grants",
            "gov_policy_bindings",
            "gov_external_references",
            "gov_traceability_edges",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("DELETE FROM gov_schema_migrations WHERE version = ?", (version,))
        conn.commit()
        return
    raise ValueError(f"rollback not supported for governance migration version {version}")
