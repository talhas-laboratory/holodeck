"""Migration 21: immutable workspace source observations."""

from __future__ import annotations

import sqlite3


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {
        str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def upgrade_source_observations(conn: sqlite3.Connection) -> None:
    """Add immutable observation history and current_observation_id pointer."""

    if not _table_exists(conn, "gov_workspace_source_observations"):
        conn.execute(
            """
            CREATE TABLE gov_workspace_source_observations (
                observation_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL
                    REFERENCES gov_workspace_sources(source_id),
                tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
                workspace_object_id TEXT NOT NULL
                    REFERENCES gov_objects(object_id),
                observed_revision TEXT NOT NULL,
                content_hash TEXT,
                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by_actor_id TEXT NOT NULL,
                schema_version TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX gov_workspace_source_observations_source
            ON gov_workspace_source_observations(source_id, observed_at)
            """
        )

    if "current_observation_id" not in _columns(conn, "gov_workspace_sources"):
        conn.execute(
            """
            ALTER TABLE gov_workspace_sources
            ADD COLUMN current_observation_id TEXT
                REFERENCES gov_workspace_source_observations(observation_id)
            """
        )

    if "conversation_context_manifest_json" not in _columns(conn, "gov_task_origins"):
        conn.execute(
            """
            ALTER TABLE gov_task_origins
            ADD COLUMN conversation_context_manifest_json TEXT
            """
        )


SOURCE_OBSERVATION_TABLES: tuple[str, ...] = ("gov_workspace_source_observations",)
