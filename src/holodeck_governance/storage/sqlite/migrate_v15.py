"""Migration 15: outbound collaboration messages correlated to outbox."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v13 import install_tenant_row_ref_triggers


def upgrade_outbound_collaboration_messages(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_outbound_collaboration_messages (
            message_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            provider TEXT NOT NULL,
            location_kind TEXT NOT NULL,
            location_reference_id TEXT NOT NULL
                REFERENCES gov_external_references(reference_id),
            parent_location_reference_id TEXT
                REFERENCES gov_external_references(reference_id),
            endpoint_id TEXT REFERENCES gov_collaboration_endpoints(endpoint_id),
            body_text TEXT NOT NULL,
            task_origin_object_id TEXT NOT NULL
                REFERENCES gov_task_origins(object_id),
            inbound_receipt_id TEXT NOT NULL
                REFERENCES gov_inbound_event_receipts(receipt_id),
            command_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            outbox_item_id TEXT NOT NULL
                REFERENCES gov_outbox_items(outbox_item_id),
            domain_event_id TEXT NOT NULL
                REFERENCES gov_domain_events(event_id),
            created_at TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            UNIQUE(tenant_id, idempotency_key)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_outbound_collab_messages_origin
        ON gov_outbound_collaboration_messages(tenant_id, task_origin_object_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_outbound_collab_messages_outbox
        ON gov_outbound_collaboration_messages(outbox_item_id)
        """
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_outbound_collaboration_messages",
        column="location_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_outbound_collaboration_messages",
        column="parent_location_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
        nullable=True,
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_outbound_collaboration_messages",
        column="endpoint_id",
        ref_table="gov_collaboration_endpoints",
        ref_pk="endpoint_id",
        nullable=True,
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_outbound_collaboration_messages",
        column="task_origin_object_id",
        ref_table="gov_task_origins",
        ref_pk="object_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_outbound_collaboration_messages",
        column="inbound_receipt_id",
        ref_table="gov_inbound_event_receipts",
        ref_pk="receipt_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_outbound_collaboration_messages",
        column="outbox_item_id",
        ref_table="gov_outbox_items",
        ref_pk="outbox_item_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_outbound_collaboration_messages",
        column="domain_event_id",
        ref_table="gov_domain_events",
        ref_pk="event_id",
    )
