from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from holodeck_control_plane.errors import ValidationError
from holodeck_control_plane.paths import format_path, normalize_path, paths_intersect

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


def _create_tasks_table(conn: sqlite3.Connection, *, with_workspace_fk: bool = False) -> None:
    workspace_fk = (
        ", FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)"
        if with_workspace_fk
        else ""
    )
    conn.execute(
        f"""
        CREATE TABLE tasks (
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK ({TASK_STATUS_CHECK}),
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (workspace_id, task_id){workspace_fk}
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


def _canonical_claim_path(path: str) -> str | None:
    try:
        return format_path(normalize_path(path))
    except ValidationError:
        return None


def _release_claim(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    run_id: str,
    payload: dict,
    released_at: str,
    reason: str,
) -> str:
    payload["run_id"] = run_id
    payload["released_at"] = released_at
    payload["release_reason"] = reason
    conn.execute(
        """
        UPDATE claims
        SET status = 'released', payload = ?, updated_at = ?
        WHERE claim_id = ?
        """,
        (json.dumps(payload), released_at, claim_id),
    )
    return run_id


def _sync_run_after_claim_release(conn: sqlite3.Connection, run_id: str, timestamp: str) -> None:
    run_row = conn.execute(
        "SELECT payload, status FROM runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if run_row is None:
        return

    run = _payload_dict(run_row["payload"])
    active_paths = [
        row["path"]
        for row in conn.execute(
            "SELECT path FROM claims WHERE run_id = ? AND status = 'active' ORDER BY created_at, claim_id",
            (run_id,),
        ).fetchall()
    ]
    run["claimed_paths"] = active_paths
    run["updated_at"] = timestamp

    if run_row["status"] == "active" and not active_paths:
        run["status"] = "failed"
        run["summary"] = str(run.get("summary") or "migration released all active claims")
        run["completed_at"] = timestamp
        conn.execute(
            "UPDATE runs SET payload = ?, status = ?, updated_at = ? WHERE run_id = ?",
            (json.dumps(run), "failed", timestamp, run_id),
        )
        return

    conn.execute(
        "UPDATE runs SET payload = ?, updated_at = ? WHERE run_id = ?",
        (json.dumps(run), timestamp, run_id),
    )


def _reconcile_claim_paths_before_index(conn: sqlite3.Connection) -> None:
    released_at = migration_now()
    affected_runs: set[str] = set()

    rows = conn.execute(
        """
        SELECT claim_id, run_id, path, payload
        FROM claims
        WHERE status = 'active'
        ORDER BY created_at ASC, claim_id ASC
        """
    ).fetchall()

    for row in rows:
        normalized = _canonical_claim_path(row["path"])
        if normalized is None:
            payload = _payload_dict(row["payload"])
            released_run_id = _release_claim(
                conn,
                claim_id=row["claim_id"],
                run_id=row["run_id"],
                payload=payload,
                released_at=released_at,
                reason="invalid_path",
            )
            if released_run_id:
                affected_runs.add(released_run_id)
            continue
        if normalized == row["path"]:
            continue
        payload = _payload_dict(row["payload"])
        payload["path"] = normalized
        conn.execute(
            "UPDATE claims SET path = ?, payload = ? WHERE claim_id = ?",
            (normalized, json.dumps(payload), row["claim_id"]),
        )
        affected_runs.add(row["run_id"])

    active_claims = conn.execute(
        """
        SELECT claim_id, workspace_id, run_id, path, payload
        FROM claims
        WHERE status = 'active'
        ORDER BY created_at ASC, claim_id ASC
        """
    ).fetchall()

    accepted_paths: dict[str, list[tuple[str, ...]]] = {}
    for claim in active_claims:
        path = normalize_path(claim["path"])
        workspace_paths = accepted_paths.setdefault(claim["workspace_id"], [])
        if any(paths_intersect(path, existing) for existing in workspace_paths):
            payload = _payload_dict(claim["payload"])
            released_run_id = _release_claim(
                conn,
                claim_id=claim["claim_id"],
                run_id=claim["run_id"],
                payload=payload,
                released_at=released_at,
                reason="overlapping_active_path",
            )
            affected_runs.add(released_run_id)
            continue
        workspace_paths.append(path)

    for run_id in affected_runs:
        _sync_run_after_claim_release(conn, run_id, released_at)


def _create_claim_safeguards(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS claims_active_path
        ON claims(workspace_id, path)
        WHERE status = 'active'
        """
    )
    conn.execute("DROP TRIGGER IF EXISTS claims_match_run_insert")
    conn.execute("DROP TRIGGER IF EXISTS claims_match_run_update")
    conn.execute(
        """
        CREATE TRIGGER claims_match_run_insert
        BEFORE INSERT ON claims
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (
                    SELECT 1 FROM runs
                    WHERE run_id = NEW.run_id
                      AND workspace_id = NEW.workspace_id
                      AND task_id = NEW.task_id
                )
                THEN RAISE(ABORT, 'claim workspace/task must match run')
            END;
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER claims_match_run_update
        BEFORE UPDATE ON claims
        BEGIN
            SELECT CASE
                WHEN NOT EXISTS (
                    SELECT 1 FROM runs
                    WHERE run_id = NEW.run_id
                      AND workspace_id = NEW.workspace_id
                      AND task_id = NEW.task_id
                )
                THEN RAISE(ABORT, 'claim workspace/task must match run')
            END;
        END
        """
    )


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


def _upgrade_workspace_fk_and_claim_safeguards(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("ALTER TABLE claims RENAME TO claims_v1")
    conn.execute("ALTER TABLE runs RENAME TO runs_v1")
    conn.execute("ALTER TABLE tasks RENAME TO tasks_v1")

    _create_tasks_table(conn, with_workspace_fk=True)
    conn.execute(
        """
        INSERT INTO tasks(workspace_id, task_id, status, payload, created_at, updated_at)
        SELECT workspace_id, task_id, status, payload, created_at, updated_at
        FROM tasks_v1
        """
    )
    _create_runs_table(conn)
    conn.execute(
        """
        INSERT INTO runs(run_id, workspace_id, task_id, status, payload, created_at, updated_at)
        SELECT run_id, workspace_id, task_id, status, payload, created_at, updated_at
        FROM runs_v1
        """
    )
    _create_claims_table(conn)
    conn.execute(
        """
        INSERT INTO claims(
            claim_id, workspace_id, task_id, run_id, path, status, payload, created_at, updated_at
        )
        SELECT claim_id, workspace_id, task_id, run_id, path, status, payload, created_at, updated_at
        FROM claims_v1
        """
    )

    conn.execute("DROP TABLE claims_v1")
    conn.execute("DROP TABLE runs_v1")
    conn.execute("DROP TABLE tasks_v1")
    _create_indexes(conn)
    _reconcile_claim_paths_before_index(conn)
    _create_claim_safeguards(conn)
    conn.execute("PRAGMA foreign_keys = ON")


def _upgrade_governed_missions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE workspace_sources (
            source_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
            revision TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE curator_proposals (
            proposal_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('delegation_contract', 'requirement')),
            status TEXT NOT NULL CHECK (status IN ('proposed', 'approved', 'rejected')),
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            decided_at TEXT,
            FOREIGN KEY (workspace_id, task_id) REFERENCES tasks(workspace_id, task_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE missions (
            mission_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('ready', 'accepted', 'rejected')),
            packet_hash TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (workspace_id, task_id) REFERENCES tasks(workspace_id, task_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE mission_evidence (
            evidence_id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL REFERENCES missions(mission_id),
            requirement_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE acceptance_decisions (
            decision_id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL UNIQUE REFERENCES missions(mission_id),
            decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX curator_proposals_task ON curator_proposals(workspace_id, task_id, status)")
    conn.execute("CREATE INDEX mission_evidence_mission ON mission_evidence(mission_id, requirement_id)")


MIGRATIONS: list[Migration] = [
    (1, "relational_integrity", _upgrade_relational_integrity),
    (2, "workspace_fk_and_claim_safeguards", _upgrade_workspace_fk_and_claim_safeguards),
    (3, "governed_missions", _upgrade_governed_missions),
]
