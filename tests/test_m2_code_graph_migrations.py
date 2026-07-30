"""M2 code-graph migration checks (v23 persistence + v24 hardening)."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v23 import CODE_GRAPH_TABLES
from holodeck_governance.storage.sqlite.migrate_v24 import CODE_GRAPH_BUILD_CLAIM_TABLES
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
    rollback_governance_migration,
)


def test_migration_creates_code_graph_tables_and_active_index() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    assert governance_schema_version(conn) >= 24
    tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for table in CODE_GRAPH_TABLES:
        assert table in tables
    for table in CODE_GRAPH_BUILD_CLAIM_TABLES:
        assert table in tables
    indexes = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "gov_code_graph_snapshots_one_active" in indexes
    assert "gov_code_entity_facts_lookup" in indexes
    assert "gov_code_relation_facts_expand" in indexes
    entity_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='gov_code_entity_facts'"
    ).fetchone()[0]
    assert "source_observation_id" in entity_sql


def test_migration_24_is_additive_from_v23_baseline() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    rollback_governance_migration(conn, 25)
    rollback_governance_migration(conn, 24)
    assert governance_schema_version(conn) == 23
    assert "gov_code_graph_build_claims" not in {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    migrate_governance(conn)
    assert governance_schema_version(conn) >= 24
    assert "gov_code_graph_build_claims" in {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
