"""Migration 17: reversible workspace-genesis proposals."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v13 import install_tenant_row_ref_triggers
from holodeck_governance.storage.sqlite.migrate_v9 import install_tenant_actor_triggers


def upgrade_workspace_genesis_proposals(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_workspace_genesis_proposals (
            proposal_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            endpoint_id TEXT NOT NULL
                REFERENCES gov_collaboration_endpoints(endpoint_id),
            location_kind TEXT NOT NULL,
            external_location_id TEXT NOT NULL,
            location_reference_id TEXT NOT NULL
                REFERENCES gov_external_references(reference_id),
            proposed_workspace_object_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            purpose_text TEXT NOT NULL,
            status TEXT NOT NULL,
            discovery_reason_codes_json TEXT NOT NULL,
            repository_provider TEXT,
            external_repository_id TEXT,
            repository_reference_id TEXT
                REFERENCES gov_external_references(reference_id),
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            decided_at TEXT,
            decided_by_actor_id TEXT,
            decision_outcome TEXT,
            decision_rationale TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    # At most one open (proposed) genesis proposal per location natural key.
    conn.execute(
        """
        CREATE UNIQUE INDEX gov_workspace_genesis_open_location
        ON gov_workspace_genesis_proposals(
            tenant_id, endpoint_id, location_kind, external_location_id
        )
        WHERE status = 'proposed'
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_workspace_genesis_tenant_created
        ON gov_workspace_genesis_proposals(tenant_id, created_at)
        """
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_workspace_genesis_proposals",
        column="endpoint_id",
        ref_table="gov_collaboration_endpoints",
        ref_pk="endpoint_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_workspace_genesis_proposals",
        column="location_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_workspace_genesis_proposals",
        column="repository_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
        nullable=True,
    )
    install_tenant_actor_triggers(
        conn,
        table="gov_workspace_genesis_proposals",
        column="created_by_actor_id",
    )
    # decided_by_actor_id is null while proposed.
    for kind, when_extra in (
        ("ins", "BEFORE INSERT ON gov_workspace_genesis_proposals"),
        (
            "upd",
            "BEFORE UPDATE OF decided_by_actor_id, tenant_id "
            "ON gov_workspace_genesis_proposals",
        ),
    ):
        name = f"gov_workspace_genesis_proposals_tenant_decided_by_actor_id_{kind}"
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            {when_extra}
            WHEN NEW.decided_by_actor_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM gov_actors a
                WHERE a.actor_id = NEW.decided_by_actor_id
                  AND a.tenant_id = NEW.tenant_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'cross-tenant authority reference forbidden: gov_workspace_genesis_proposals.decided_by_actor_id'
                );
            END
            """
        )
