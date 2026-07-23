from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]

BUSY_TIMEOUT_MS = 5000

TASK_STATUSES = frozenset(
    {"backlog", "ready", "in-progress", "review", "blocked", "done", "cancelled"}
)
RUN_STATUSES = frozenset({"active", "completed", "failed", "cancelled"})
CLAIM_STATUSES = frozenset({"active", "released"})

TASK_STATUS_CHECK = (
    "status IN ('backlog', 'ready', 'in-progress', 'review', 'blocked', 'done', 'cancelled')"
)
RUN_STATUS_CHECK = "status IN ('active', 'completed', 'failed', 'cancelled')"
CLAIM_STATUS_CHECK = "status IN ('active', 'released')"


def migration_now() -> str:
    return datetime.now(UTC).isoformat()


def configure_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")


def migrate(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {
        int(row[0])
        for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    }
    for version, _name, upgrade in MIGRATIONS:
        if version in applied:
            continue
        previous_isolation = conn.isolation_level
        conn.isolation_level = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            upgrade(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, migration_now()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.isolation_level = previous_isolation


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, name: str) -> set[str]:
    if not _table_exists(conn, name):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({name})").fetchall()}


def _is_legacy_schema(conn: sqlite3.Connection) -> bool:
    task_columns = _table_columns(conn, "tasks")
    claim_columns = _table_columns(conn, "claims")
    if not task_columns:
        return False
    if "run_id" in claim_columns:
        return False
    return task_columns == {"task_id", "workspace_id", "payload", "created_at", "updated_at"}


def _create_workspaces_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _create_tasks_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE tasks (
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK ({TASK_STATUS_CHECK}),
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (workspace_id, task_id)
        )
        """
    )


def _create_runs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK ({RUN_STATUS_CHECK}),
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (workspace_id, task_id) REFERENCES tasks(workspace_id, task_id)
        )
        """
    )


def _create_claims_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE claims (
            claim_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL CHECK ({CLAIM_STATUS_CHECK}),
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (workspace_id, task_id) REFERENCES tasks(workspace_id, task_id)
        )
        """
    )


def _create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS tasks_workspace ON tasks(workspace_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS runs_workspace ON runs(workspace_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS runs_task ON runs(workspace_id, task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS claims_workspace ON claims(workspace_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS claims_run ON claims(run_id, status)")


def _create_relational_schema(conn: sqlite3.Connection) -> None:
    _create_workspaces_table(conn)
    if not _table_exists(conn, "tasks"):
        _create_tasks_table(conn)
    if not _table_exists(conn, "runs"):
        _create_runs_table(conn)
    if not _table_exists(conn, "claims"):
        _create_claims_table(conn)
    _create_indexes(conn)


def _payload_dict(payload: str) -> dict:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _payload_status(payload: str, default: str) -> str:
    return str(_payload_dict(payload).get("status") or default)


def _coerce_task_status(status: str) -> str:
    return status if status in TASK_STATUSES else "backlog"


def _coerce_run_status(status: str) -> str:
    return status if status in RUN_STATUSES else "active"


def _coerce_claim_status(status: str) -> str:
    return status if status in CLAIM_STATUSES else "released"


def _with_status(payload: str, status: str) -> str:
    data = _payload_dict(payload)
    data["status"] = status
    return json.dumps(data)


def _upgrade_legacy_schema(conn: sqlite3.Connection) -> None:
    tasks = conn.execute("SELECT task_id, workspace_id, payload, created_at, updated_at FROM tasks").fetchall()
    runs = conn.execute("SELECT run_id, workspace_id, task_id, payload, created_at, updated_at FROM runs").fetchall()
    claims = conn.execute(
        "SELECT claim_id, workspace_id, task_id, path, status, payload, created_at, updated_at FROM claims"
    ).fetchall()

    prepared_tasks = []
    for row in tasks:
        status = _coerce_task_status(_payload_status(row["payload"], "backlog"))
        prepared_tasks.append(
            (
                row["workspace_id"],
                row["task_id"],
                status,
                _with_status(row["payload"], status),
                row["created_at"],
                row["updated_at"],
            )
        )

    prepared_runs = []
    for row in runs:
        status = _coerce_run_status(_payload_status(row["payload"], "active"))
        prepared_runs.append(
            (
                row["run_id"],
                row["workspace_id"],
                row["task_id"],
                status,
                _with_status(row["payload"], status),
                row["created_at"],
                row["updated_at"],
            )
        )

    prepared_claims = []
    for row in claims:
        payload = _payload_dict(row["payload"])
        run_id = str(payload.get("run_id") or "")
        if not run_id:
            raise RuntimeError(f"legacy claim missing run_id: {row['claim_id']}")
        status = _coerce_claim_status(str(row["status"]))
        payload["run_id"] = run_id
        prepared_claims.append(
            (
                row["claim_id"],
                row["workspace_id"],
                row["task_id"],
                run_id,
                row["path"],
                status,
                json.dumps(payload),
                row["created_at"],
                row["updated_at"],
            )
        )

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("ALTER TABLE claims RENAME TO claims_legacy")
    conn.execute("ALTER TABLE runs RENAME TO runs_legacy")
    conn.execute("ALTER TABLE tasks RENAME TO tasks_legacy")
    _create_tasks_table(conn)
    _create_runs_table(conn)
    _create_claims_table(conn)
    conn.executemany(
        "INSERT INTO tasks(workspace_id, task_id, status, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        prepared_tasks,
    )
    conn.executemany(
        "INSERT INTO runs(run_id, workspace_id, task_id, status, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        prepared_runs,
    )
    conn.executemany(
        """
        INSERT INTO claims(
            claim_id, workspace_id, task_id, run_id, path, status, payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        prepared_claims,
    )
    conn.execute("DROP TABLE claims_legacy")
    conn.execute("DROP TABLE runs_legacy")
    conn.execute("DROP TABLE tasks_legacy")
    _create_indexes(conn)
    conn.execute("PRAGMA foreign_keys = ON")


def _upgrade_relational_integrity(conn: sqlite3.Connection) -> None:
    if _is_legacy_schema(conn):
        _upgrade_legacy_schema(conn)
        return
    _create_relational_schema(conn)


MIGRATIONS: list[Migration] = [
    (1, "relational_integrity", _upgrade_relational_integrity),
]
