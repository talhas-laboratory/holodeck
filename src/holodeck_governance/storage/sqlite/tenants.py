"""SQLite tenant repository and default-tenant bootstrap."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.metadata import GovernanceMetadata
from holodeck_governance.domain.tenant import (
    DEFAULT_LOCAL_TENANT_SCHEMA,
    DEFAULT_LOCAL_TENANT_SLUG,
    Tenant,
    build_default_local_tenant,
)
from holodeck_governance.storage.sqlite.migrations import migrate_governance


class SqliteTenantRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def get(self, tenant_id: str) -> Tenant | None:
        row = self._conn.execute(
            "SELECT * FROM gov_tenants WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        return _row_to_tenant(row) if row else None

    def get_default_local(self) -> Tenant | None:
        row = self._conn.execute(
            "SELECT * FROM gov_tenants WHERE is_default_local = 1"
        ).fetchone()
        return _row_to_tenant(row) if row else None

    def save(self, tenant: Tenant) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_tenants(
                tenant_id, slug, display_name, schema_version, created_at,
                created_by_actor_id, provenance_ref, status, is_default_local
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id) DO UPDATE SET
                slug=excluded.slug,
                display_name=excluded.display_name,
                schema_version=excluded.schema_version,
                status=excluded.status,
                is_default_local=excluded.is_default_local
            """,
            (
                tenant.id,
                tenant.slug,
                tenant.display_name,
                tenant.metadata.schema_version,
                tenant.metadata.created_at.isoformat(),
                tenant.metadata.created_by_actor_id,
                tenant.metadata.provenance_ref,
                tenant.metadata.status or "active",
                1 if tenant.is_default_local else 0,
            ),
        )

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM gov_tenants").fetchone()
        return int(row["n"])


def ensure_default_local_tenant(
    conn: sqlite3.Connection,
    *,
    created_by_actor_id: str | None = None,
    created_at: datetime | None = None,
    tenant_id: str | None = None,
) -> Tenant:
    """Migrate governance schema and ensure exactly one default local tenant."""

    migrate_governance(conn)
    repo = SqliteTenantRepository(conn)
    existing = repo.get_default_local()
    if existing is not None:
        return existing
    actor_id = created_by_actor_id or generate_uuidv7()
    tenant = build_default_local_tenant(
        tenant_id=tenant_id or generate_uuidv7(),
        created_by_actor_id=actor_id,
        created_at=created_at or datetime.now(UTC),
    )
    repo.save(tenant)
    conn.commit()
    return tenant


def _row_to_tenant(row: sqlite3.Row) -> Tenant:
    created_at = datetime.fromisoformat(str(row["created_at"]))
    metadata = GovernanceMetadata(
        id=str(row["tenant_id"]),
        tenant_id=str(row["tenant_id"]),
        schema_version=str(row["schema_version"]),
        created_at=created_at,
        created_by_actor_id=str(row["created_by_actor_id"]),
        provenance_ref=row["provenance_ref"],
        status=str(row["status"]),
    )
    return Tenant(
        metadata=metadata,
        slug=str(row["slug"]),
        display_name=str(row["display_name"]),
        is_default_local=bool(row["is_default_local"]),
    )


# Re-export constants used by tests
__all__ = [
    "SqliteTenantRepository",
    "ensure_default_local_tenant",
    "DEFAULT_LOCAL_TENANT_SLUG",
    "DEFAULT_LOCAL_TENANT_SCHEMA",
]
