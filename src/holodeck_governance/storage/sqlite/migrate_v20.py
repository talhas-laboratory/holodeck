"""Migration 20: durable promotion_decision_id on workspace sources."""

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


def upgrade_source_promotion_decision(conn: sqlite3.Connection) -> None:
    """Persist the WorkspaceDecision used for elevated trust promotions."""

    if "promotion_decision_id" in _columns(conn, "gov_workspace_sources"):
        return
    conn.execute(
        """
        ALTER TABLE gov_workspace_sources
        ADD COLUMN promotion_decision_id TEXT
            REFERENCES gov_workspace_decisions(decision_id)
        """
    )
