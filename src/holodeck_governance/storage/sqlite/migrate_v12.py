"""Migration 12: durable task origins with source-thread context."""

from __future__ import annotations

import sqlite3


def upgrade_task_origins(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_task_origins (
            object_id TEXT PRIMARY KEY REFERENCES gov_objects(object_id),
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            actor_id TEXT NOT NULL REFERENCES gov_actors(actor_id),
            inbound_receipt_id TEXT NOT NULL UNIQUE
                REFERENCES gov_inbound_event_receipts(receipt_id),
            source_reference_id TEXT NOT NULL
                REFERENCES gov_external_references(reference_id),
            provider TEXT NOT NULL,
            external_event_id TEXT NOT NULL,
            subject_text TEXT NOT NULL,
            body_text TEXT NOT NULL,
            location_kind TEXT NOT NULL,
            location_reference_id TEXT NOT NULL
                REFERENCES gov_external_references(reference_id),
            parent_location_reference_id TEXT
                REFERENCES gov_external_references(reference_id),
            endpoint_id TEXT REFERENCES gov_collaboration_endpoints(endpoint_id),
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            adapter_metadata_json TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            UNIQUE(tenant_id, provider, external_event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_task_origins_tenant_created
        ON gov_task_origins(tenant_id, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_task_origins_receipt
        ON gov_task_origins(inbound_receipt_id)
        """
    )
