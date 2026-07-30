"""Migration 11: collaboration endpoints, actor mappings, inbound receipts."""

from __future__ import annotations

import sqlite3


def upgrade_collaboration_bindings_and_receipts(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_collaboration_endpoints (
            endpoint_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            provider TEXT NOT NULL,
            external_endpoint_id TEXT NOT NULL,
            locator TEXT NOT NULL,
            display_name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            adapter_metadata_json TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            UNIQUE(tenant_id, provider, external_endpoint_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_external_actor_mappings (
            mapping_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            endpoint_id TEXT NOT NULL REFERENCES gov_collaboration_endpoints(endpoint_id),
            actor_id TEXT NOT NULL REFERENCES gov_actors(actor_id),
            provider TEXT NOT NULL,
            external_actor_id TEXT NOT NULL,
            external_identity_reference_id TEXT NOT NULL
                REFERENCES gov_external_references(reference_id),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            adapter_metadata_json TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            UNIQUE(tenant_id, provider, external_actor_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_inbound_event_receipts (
            receipt_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            provider TEXT NOT NULL,
            external_event_id TEXT NOT NULL,
            inbound_event_id TEXT NOT NULL,
            signed_source_reference_id TEXT NOT NULL
                REFERENCES gov_external_references(reference_id),
            verification_result TEXT NOT NULL,
            processing_outcome TEXT NOT NULL,
            reason_codes_json TEXT NOT NULL,
            checkpoint_token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            command_id TEXT,
            task_origin_object_id TEXT,
            endpoint_id TEXT REFERENCES gov_collaboration_endpoints(endpoint_id),
            schema_version TEXT NOT NULL,
            UNIQUE(tenant_id, provider, external_event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_inbound_event_receipts_tenant_created
        ON gov_inbound_event_receipts(tenant_id, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_external_actor_mappings_actor
        ON gov_external_actor_mappings(tenant_id, actor_id)
        """
    )
