"""Validated persistence for traceability edges (M1-009)."""

from __future__ import annotations

import sqlite3

from holodeck_governance.domain.edges import TraceabilityEdge, validate_edge_endpoints
from holodeck_governance.domain.errors import EdgeValidationError
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository


class SqliteEdgeRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        migrate_governance(conn)
        self._revisions = SqliteRevisionRepository(conn)

    def save(self, edge: TraceabilityEdge) -> None:
        from_object = self._revisions.get_object(edge.from_object_id)
        to_object = self._revisions.get_object(edge.to_object_id)
        validate_edge_endpoints(edge, from_object=from_object, to_object=to_object)
        if self._revisions.get_revision(edge.from_object_id, edge.from_revision) is None:
            raise EdgeValidationError(
                f"missing from revision {edge.from_object_id}@{edge.from_revision}"
            )
        if self._revisions.get_revision(edge.to_object_id, edge.to_revision) is None:
            raise EdgeValidationError(
                f"missing to revision {edge.to_object_id}@{edge.to_revision}"
            )
        self._conn.execute(
            """
            INSERT INTO gov_traceability_edges(
                edge_id, tenant_id, edge_type, from_object_id, from_revision,
                to_object_id, to_revision, created_at, created_by_actor_id,
                provenance_ref, validity_status, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edge.edge_id,
                edge.tenant_id,
                edge.edge_type,
                edge.from_object_id,
                edge.from_revision,
                edge.to_object_id,
                edge.to_revision,
                edge.created_at.isoformat(),
                edge.created_by_actor_id,
                edge.provenance_ref,
                edge.validity_status,
                edge.schema_version,
            ),
        )
