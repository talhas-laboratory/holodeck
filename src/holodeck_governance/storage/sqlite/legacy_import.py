"""Legacy import helpers for GS-014 (M1-023)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.legacy_mapping import map_legacy_status
from holodeck_governance.storage.legacy_seam import PROVENANCE_KIND
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant


@dataclass(frozen=True, slots=True)
class ImportedLegacyTask:
    legacy_task_id: str
    legacy_workspace_id: str
    legacy_status: str
    m1_state: str
    m1_object_id: str
    provenance_kind: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ImportedLegacyRun:
    legacy_run_id: str
    legacy_workspace_id: str
    legacy_task_id: str
    legacy_status: str
    m1_state: str
    m1_object_id: str
    provenance_kind: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ImportedLegacyWorkspace:
    legacy_workspace_id: str
    m1_object_id: str
    provenance_kind: str
    created_at: str


@dataclass(frozen=True, slots=True)
class LegacyImportReport:
    workspaces: tuple[ImportedLegacyWorkspace, ...]
    tasks: tuple[ImportedLegacyTask, ...]
    runs: tuple[ImportedLegacyRun, ...]


def _ensure_import_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gov_legacy_workspace_imports (
            import_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            legacy_workspace_id TEXT NOT NULL,
            m1_object_id TEXT NOT NULL,
            provenance_kind TEXT NOT NULL,
            legacy_created_at TEXT,
            imported_at TEXT NOT NULL,
            UNIQUE(tenant_id, legacy_workspace_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gov_legacy_task_imports (
            import_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            legacy_workspace_id TEXT NOT NULL,
            legacy_task_id TEXT NOT NULL,
            legacy_status TEXT NOT NULL,
            m1_state TEXT NOT NULL,
            m1_object_id TEXT NOT NULL,
            provenance_kind TEXT NOT NULL,
            legacy_created_at TEXT,
            imported_at TEXT NOT NULL,
            UNIQUE(tenant_id, legacy_workspace_id, legacy_task_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gov_legacy_run_imports (
            import_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            legacy_workspace_id TEXT NOT NULL,
            legacy_task_id TEXT NOT NULL,
            legacy_run_id TEXT NOT NULL,
            legacy_status TEXT NOT NULL,
            m1_state TEXT NOT NULL,
            m1_object_id TEXT NOT NULL,
            provenance_kind TEXT NOT NULL,
            legacy_created_at TEXT,
            imported_at TEXT NOT NULL,
            UNIQUE(tenant_id, legacy_workspace_id, legacy_run_id)
        )
        """
    )


def import_legacy_workspaces(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    actor_id: str,
) -> list[ImportedLegacyWorkspace]:
    ensure_default_local_tenant(conn, tenant_id=tenant_id, created_by_actor_id=actor_id)
    migrate_governance(conn)
    _ensure_import_tables(conn)
    rows = conn.execute(
        "SELECT workspace_id, created_at FROM workspaces ORDER BY created_at, workspace_id"
    ).fetchall()
    imported: list[ImportedLegacyWorkspace] = []
    now = datetime.now().astimezone().isoformat()
    for row in rows:
        object_id = generate_uuidv7()
        conn.execute(
            """
            INSERT OR IGNORE INTO gov_legacy_workspace_imports(
                import_id, tenant_id, legacy_workspace_id, m1_object_id,
                provenance_kind, legacy_created_at, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_uuidv7(),
                tenant_id,
                str(row[0]),
                object_id,
                PROVENANCE_KIND,
                str(row[1]),
                now,
            ),
        )
        imported.append(
            ImportedLegacyWorkspace(
                legacy_workspace_id=str(row[0]),
                m1_object_id=object_id,
                provenance_kind=PROVENANCE_KIND,
                created_at=str(row[1]),
            )
        )
    conn.commit()
    return imported


def import_legacy_tasks(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    actor_id: str,
) -> list[ImportedLegacyTask]:
    """Import M0 tasks as legacy_import facts without inventing authority."""

    ensure_default_local_tenant(conn, tenant_id=tenant_id, created_by_actor_id=actor_id)
    migrate_governance(conn)
    _ensure_import_tables(conn)
    rows = conn.execute(
        "SELECT workspace_id, task_id, status, created_at FROM tasks ORDER BY created_at, task_id"
    ).fetchall()
    imported: list[ImportedLegacyTask] = []
    now = datetime.now().astimezone().isoformat()
    for row in rows:
        mapping = map_legacy_status("task", str(row[2]))
        object_id = generate_uuidv7()
        conn.execute(
            """
            INSERT OR IGNORE INTO gov_legacy_task_imports(
                import_id, tenant_id, legacy_workspace_id, legacy_task_id, legacy_status,
                m1_state, m1_object_id, provenance_kind, legacy_created_at, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_uuidv7(),
                tenant_id,
                str(row[0]),
                str(row[1]),
                str(row[2]),
                mapping.m1_value,
                object_id,
                PROVENANCE_KIND,
                str(row[3]),
                now,
            ),
        )
        imported.append(
            ImportedLegacyTask(
                legacy_task_id=str(row[1]),
                legacy_workspace_id=str(row[0]),
                legacy_status=str(row[2]),
                m1_state=str(mapping.m1_value),
                m1_object_id=object_id,
                provenance_kind=PROVENANCE_KIND,
                created_at=str(row[3]),
            )
        )
    conn.commit()
    return imported


def import_legacy_runs(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    actor_id: str,
) -> list[ImportedLegacyRun]:
    ensure_default_local_tenant(conn, tenant_id=tenant_id, created_by_actor_id=actor_id)
    migrate_governance(conn)
    _ensure_import_tables(conn)
    rows = conn.execute(
        """
        SELECT workspace_id, task_id, run_id, status, created_at
        FROM runs
        ORDER BY created_at, run_id
        """
    ).fetchall()
    imported: list[ImportedLegacyRun] = []
    now = datetime.now().astimezone().isoformat()
    for row in rows:
        mapping = map_legacy_status("run", str(row[3]))
        object_id = generate_uuidv7()
        conn.execute(
            """
            INSERT OR IGNORE INTO gov_legacy_run_imports(
                import_id, tenant_id, legacy_workspace_id, legacy_task_id, legacy_run_id,
                legacy_status, m1_state, m1_object_id, provenance_kind,
                legacy_created_at, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_uuidv7(),
                tenant_id,
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                mapping.m1_value,
                object_id,
                PROVENANCE_KIND,
                str(row[4]),
                now,
            ),
        )
        imported.append(
            ImportedLegacyRun(
                legacy_run_id=str(row[2]),
                legacy_workspace_id=str(row[0]),
                legacy_task_id=str(row[1]),
                legacy_status=str(row[3]),
                m1_state=str(mapping.m1_value),
                m1_object_id=object_id,
                provenance_kind=PROVENANCE_KIND,
                created_at=str(row[4]),
            )
        )
    conn.commit()
    return imported


def import_legacy_database(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    actor_id: str,
) -> LegacyImportReport:
    """Upgrade-path import for workspaces, tasks, and runs without inventing authority."""

    workspaces = import_legacy_workspaces(conn, tenant_id=tenant_id, actor_id=actor_id)
    tasks = import_legacy_tasks(conn, tenant_id=tenant_id, actor_id=actor_id)
    runs = import_legacy_runs(conn, tenant_id=tenant_id, actor_id=actor_id)
    return LegacyImportReport(
        workspaces=tuple(workspaces),
        tasks=tuple(tasks),
        runs=tuple(runs),
    )
