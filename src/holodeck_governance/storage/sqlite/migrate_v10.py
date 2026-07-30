"""Migration 10: explicit, inspectable authority-record issuance basis."""

from __future__ import annotations

import sqlite3


def _add(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def upgrade_authority_issuance_basis(conn: sqlite3.Connection) -> None:
    # Nullable historical rows are intentionally fail-closed by the repository:
    # M1 cannot invent a basis for authority that predates this migration.
    _add(conn, "gov_delegated_grants", "issuance_basis_kind", "TEXT")
    _add(conn, "gov_delegated_grants", "issuance_basis_id", "TEXT")
    _add(conn, "gov_revocation_decisions", "issuance_basis_kind", "TEXT")
    _add(conn, "gov_revocation_decisions", "issuance_basis_id", "TEXT")
