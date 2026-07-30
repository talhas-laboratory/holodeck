"""Migration 6: align pre-v5.1 record-family columns with domain records."""

from __future__ import annotations

import sqlite3


def upgrade_record_family_alignment(conn: sqlite3.Connection) -> None:
    tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "gov_runs" in tables:
        run_cols = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(gov_runs)").fetchall()
        }
        if "mission_object_id" not in run_cols:
            conn.execute("ALTER TABLE gov_runs ADD COLUMN mission_object_id TEXT")

    if "gov_role_profiles" in tables:
        role_cols = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(gov_role_profiles)").fetchall()
        }
        if "jurisdiction_json" not in role_cols:
            conn.execute(
                """
                ALTER TABLE gov_role_profiles
                ADD COLUMN jurisdiction_json TEXT NOT NULL DEFAULT '{}'
                """
            )

    if "gov_evidence" not in tables:
        return

    evidence_cols = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(gov_evidence)").fetchall()
    }
    if "requirement_object_id" in evidence_cols and "artifact_object_id" in evidence_cols:
        return

    existing = int(conn.execute("SELECT COUNT(*) FROM gov_evidence").fetchone()[0])
    if existing > 0:
        # Fail closed: never drop a populated evidence table that cannot be mapped.
        raise RuntimeError(
            "migrate_v6 cannot rewrite non-empty gov_evidence missing "
            "requirement_object_id/artifact_object_id; preserve existing data"
        )

    conn.execute(
        """
        CREATE TABLE gov_evidence_v6 (
            record_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            requirement_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            artifact_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            content_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            UNIQUE(object_id, revision)
        )
        """
    )
    conn.execute("DROP TABLE IF EXISTS gov_evidence")
    conn.execute("ALTER TABLE gov_evidence_v6 RENAME TO gov_evidence")
