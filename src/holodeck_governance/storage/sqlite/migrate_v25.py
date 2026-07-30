"""Migration 25: backfill observation pointers for pre-v21 sources."""

from __future__ import annotations

import sqlite3

from holodeck_governance.domain.ids import generate_uuidv7


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


def upgrade_legacy_source_observation_backfill(conn: sqlite3.Connection) -> None:
    """Assign immutable observations to live sources that lack a pointer.

    Migration 21 added ``current_observation_id`` without backfilling rows created
    under v19/v20. Ordinary reads later began treating null pointers as invisible.
    This backfill creates one observation per unpointed, non-staged source from
    its existing revision metadata and points the source at it.
    """

    if not _table_exists(conn, "gov_workspace_sources"):
        return
    if not _table_exists(conn, "gov_workspace_source_observations"):
        return
    if "current_observation_id" not in _columns(conn, "gov_workspace_sources"):
        return

    previous_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT source_id, tenant_id, workspace_object_id, observed_revision,
                   content_hash, observed_at, created_at, created_by_actor_id
            FROM gov_workspace_sources
            WHERE current_observation_id IS NULL
              AND stale_status != 'staged'
            ORDER BY created_at, source_id
            """
        ).fetchall()
        for row in rows:
            observation_id = generate_uuidv7()
            content_hash = row["content_hash"]
            conn.execute(
                """
                INSERT INTO gov_workspace_source_observations(
                    observation_id, source_id, tenant_id, workspace_object_id,
                    observed_revision, content_hash, observed_at, created_at,
                    created_by_actor_id, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    str(row["source_id"]),
                    str(row["tenant_id"]),
                    str(row["workspace_object_id"]),
                    str(row["observed_revision"]),
                    None if content_hash is None else str(content_hash),
                    str(row["observed_at"]),
                    str(row["created_at"]),
                    str(row["created_by_actor_id"]),
                    "m2.workspace_source_observation.v1",
                ),
            )
            conn.execute(
                """
                UPDATE gov_workspace_sources
                SET current_observation_id = ?
                WHERE source_id = ?
                  AND current_observation_id IS NULL
                """,
                (observation_id, str(row["source_id"])),
            )
    finally:
        conn.row_factory = previous_factory
