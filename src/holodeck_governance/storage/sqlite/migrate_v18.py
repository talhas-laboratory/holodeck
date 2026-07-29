"""Migration 18: active-only unique indexes for workspace bindings."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v13 import install_tenant_row_ref_triggers
from holodeck_governance.storage.sqlite.migrate_v8 import install_tenant_object_triggers
from holodeck_governance.storage.sqlite.migrate_v9 import install_tenant_actor_triggers


def upgrade_workspace_binding_active_uniques(conn: sqlite3.Connection) -> None:
    """Replace global unique natural keys with active-only partial uniques.

    Historical retired/proposed rows remain; at most one active binding may exist
    per repository or collaboration-location natural key.
    """

    conn.execute(
        """
        CREATE TABLE gov_repository_bindings_v18 (
            binding_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            provider TEXT NOT NULL,
            external_repository_id TEXT NOT NULL,
            canonical_locator TEXT NOT NULL,
            default_branch TEXT NOT NULL,
            status TEXT NOT NULL,
            external_reference_id TEXT NOT NULL
                REFERENCES gov_external_references(reference_id),
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO gov_repository_bindings_v18(
            binding_id, tenant_id, workspace_object_id, provider,
            external_repository_id, canonical_locator, default_branch, status,
            external_reference_id, created_at, created_by_actor_id, schema_version
        )
        SELECT
            binding_id, tenant_id, workspace_object_id, provider,
            external_repository_id, canonical_locator, default_branch, status,
            external_reference_id, created_at, created_by_actor_id, schema_version
        FROM gov_repository_bindings
        """
    )
    conn.execute("DROP TABLE gov_repository_bindings")
    conn.execute("ALTER TABLE gov_repository_bindings_v18 RENAME TO gov_repository_bindings")
    conn.execute(
        """
        CREATE UNIQUE INDEX gov_repository_bindings_active_natural
        ON gov_repository_bindings(tenant_id, provider, external_repository_id)
        WHERE status = 'active'
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_repository_bindings_workspace
        ON gov_repository_bindings(tenant_id, workspace_object_id)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_collaboration_location_bindings_v18 (
            binding_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            endpoint_id TEXT NOT NULL
                REFERENCES gov_collaboration_endpoints(endpoint_id),
            location_kind TEXT NOT NULL,
            external_location_id TEXT NOT NULL,
            location_reference_id TEXT NOT NULL
                REFERENCES gov_external_references(reference_id),
            intake_policy_id TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO gov_collaboration_location_bindings_v18(
            binding_id, tenant_id, workspace_object_id, endpoint_id, location_kind,
            external_location_id, location_reference_id, intake_policy_id, status,
            created_at, created_by_actor_id, schema_version
        )
        SELECT
            binding_id, tenant_id, workspace_object_id, endpoint_id, location_kind,
            external_location_id, location_reference_id, intake_policy_id, status,
            created_at, created_by_actor_id, schema_version
        FROM gov_collaboration_location_bindings
        """
    )
    conn.execute("DROP TABLE gov_collaboration_location_bindings")
    conn.execute(
        "ALTER TABLE gov_collaboration_location_bindings_v18 "
        "RENAME TO gov_collaboration_location_bindings"
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX gov_collab_location_bindings_active_natural
        ON gov_collaboration_location_bindings(
            tenant_id, endpoint_id, location_kind, external_location_id
        )
        WHERE status = 'active'
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_collab_location_bindings_workspace
        ON gov_collaboration_location_bindings(tenant_id, workspace_object_id)
        """
    )

    install_tenant_object_triggers(
        conn, table="gov_repository_bindings", column="workspace_object_id"
    )
    install_tenant_actor_triggers(
        conn, table="gov_repository_bindings", column="created_by_actor_id"
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_repository_bindings",
        column="external_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
    )
    install_tenant_object_triggers(
        conn,
        table="gov_collaboration_location_bindings",
        column="workspace_object_id",
    )
    install_tenant_actor_triggers(
        conn,
        table="gov_collaboration_location_bindings",
        column="created_by_actor_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_collaboration_location_bindings",
        column="endpoint_id",
        ref_table="gov_collaboration_endpoints",
        ref_pk="endpoint_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_collaboration_location_bindings",
        column="location_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
    )
