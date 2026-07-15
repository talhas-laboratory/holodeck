from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    """Small SQLite authority with explicit, portable JSON records."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS tasks_workspace ON tasks(workspace_id);
                CREATE INDEX IF NOT EXISTS runs_workspace ON runs(workspace_id);
                CREATE INDEX IF NOT EXISTS claims_workspace ON claims(workspace_id, status);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        return dict(json.loads(row["payload"]))

    def catalog(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM workspaces ORDER BY created_at DESC").fetchall()
        return [self._decode(row) for row in rows]

    def create_workspace(self, manifest: dict[str, Any]) -> dict[str, Any]:
        workspace_id = str(manifest.get("workspace_id", "")).strip()
        if not workspace_id:
            raise ValueError("workspace_id is required")
        timestamp = now()
        payload = {
            "workspace_id": workspace_id,
            "label": str(manifest.get("label") or workspace_id),
            "goal": str(manifest.get("goal", "")),
            "purpose": str(manifest.get("purpose", "")),
            "artifact_roots": list(manifest.get("artifact_roots", []) or []),
            "scope_out": list(manifest.get("scope_out", []) or []),
            "status": "active",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone():
                raise ValueError(f"workspace already exists: {workspace_id}")
            conn.execute(
                "INSERT INTO workspaces VALUES (?, ?, ?, ?)",
                (workspace_id, json.dumps(payload), timestamp, timestamp),
            )
        return payload

    def workspace(self, workspace_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone()
        if row is None:
            raise KeyError(f"workspace not found: {workspace_id}")
        return self._decode(row)

    def update_workspace(self, workspace_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        current = self.workspace(workspace_id)
        for field in ("label", "goal", "purpose"):
            if field in changes:
                current[field] = str(changes[field])
        for field in ("artifact_roots", "scope_out"):
            if field in changes:
                current[field] = [str(value) for value in list(changes[field] or []) if str(value).strip()]
        current["updated_at"] = now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE workspaces SET payload = ?, updated_at = ? WHERE workspace_id = ?",
                (json.dumps(current), current["updated_at"], workspace_id),
            )
        return current

    def tasks(self, workspace_id: str) -> list[dict[str, Any]]:
        self.workspace(workspace_id)
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM tasks WHERE workspace_id = ? ORDER BY created_at", (workspace_id,)).fetchall()
        return [self._decode(row) for row in rows]

    def create_task(self, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.workspace(workspace_id)
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValueError("title is required")
        timestamp = now()
        task = {
            "task_id": str(payload.get("task_id") or f"task-{uuid.uuid4().hex[:12]}"),
            "workspace_id": workspace_id,
            "title": title,
            "status": str(payload.get("status") or "backlog"),
            "acceptance_criteria": list(payload.get("acceptance_criteria", []) or []),
            "constraints": list(payload.get("constraints", []) or []),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self._connect() as conn:
            conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?)", (task["task_id"], workspace_id, json.dumps(task), timestamp, timestamp))
        return task

    def task(self, workspace_id: str, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM tasks WHERE workspace_id = ? AND task_id = ?",
                (workspace_id, task_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"task not found: {task_id}")
        return self._decode(row)

    def update_task(self, workspace_id: str, task_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        task = self.task(workspace_id, task_id)
        if "title" in changes:
            title = str(changes["title"]).strip()
            if not title:
                raise ValueError("title is required")
            task["title"] = title
        if "status" in changes:
            task["status"] = str(changes["status"]).strip()
        for field in ("acceptance_criteria", "constraints"):
            if field in changes:
                task[field] = [str(value) for value in list(changes[field] or []) if str(value).strip()]
        task["updated_at"] = now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET payload = ?, updated_at = ? WHERE workspace_id = ? AND task_id = ?",
                (json.dumps(task), task["updated_at"], workspace_id, task_id),
            )
        return task

    @staticmethod
    def _overlaps(left: str, right: str) -> bool:
        return left == right or left.startswith(right.rstrip("/") + "/") or right.startswith(left.rstrip("/") + "/")

    def begin_run(self, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = str(payload.get("task_id", "")).strip()
        if task_id not in {task["task_id"] for task in self.tasks(workspace_id)}:
            raise ValueError("task_id must identify a task in this workspace")
        paths = [str(path).strip() for path in list(payload.get("claimed_paths", []) or []) if str(path).strip()]
        with self._connect() as conn:
            active = conn.execute("SELECT path FROM claims WHERE workspace_id = ? AND status = 'active'", (workspace_id,)).fetchall()
            for path in paths:
                if any(self._overlaps(path, row["path"]) for row in active):
                    raise ValueError(f"claimed path overlaps active work: {path}")
            timestamp = now()
            run = {
                "run_id": f"run-{uuid.uuid4().hex[:12]}",
                "workspace_id": workspace_id,
                "task_id": task_id,
                "agent_id": str(payload.get("agent_id") or "unknown"),
                "intent": str(payload.get("intent", "")),
                "status": "active",
                "claimed_paths": paths,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            conn.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)", (run["run_id"], workspace_id, task_id, json.dumps(run), timestamp, timestamp))
            for path in paths:
                claim = {
                    "claim_id": f"claim-{uuid.uuid4().hex[:12]}",
                    "workspace_id": workspace_id,
                    "task_id": task_id,
                    "run_id": run["run_id"],
                    "agent_id": run["agent_id"],
                    "path": path,
                }
                conn.execute("INSERT INTO claims VALUES (?, ?, ?, ?, 'active', ?, ?, ?)", (claim["claim_id"], workspace_id, task_id, path, json.dumps(claim), timestamp, timestamp))
        return run

    def runs(self, workspace_id: str) -> list[dict[str, Any]]:
        self.workspace(workspace_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM runs WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def claims(self, workspace_id: str) -> list[dict[str, Any]]:
        self.workspace(workspace_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload, workspace_id, task_id, status, created_at, updated_at FROM claims WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
        claims = []
        for row in rows:
            claim = self._decode(row)
            claim.update(
                {
                    "workspace_id": row["workspace_id"],
                    "task_id": row["task_id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
            claims.append(claim)
        return claims

    def complete_run(self, workspace_id: str, run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM runs WHERE workspace_id = ? AND run_id = ?",
                (workspace_id, run_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"run not found: {run_id}")
            run = self._decode(row)
            if run["status"] != "active":
                raise ValueError(f"run is already {run['status']}")
            timestamp = now()
            result = dict(payload or {})
            run.update(
                {
                    "status": str(result.get("status") or "completed"),
                    "summary": str(result.get("summary") or ""),
                    "updated_at": timestamp,
                    "completed_at": timestamp,
                }
            )
            conn.execute(
                "UPDATE runs SET payload = ?, updated_at = ? WHERE workspace_id = ? AND run_id = ?",
                (json.dumps(run), timestamp, workspace_id, run_id),
            )
            claim_rows = conn.execute(
                "SELECT claim_id, payload FROM claims WHERE workspace_id = ? AND payload LIKE ? AND status = 'active'",
                (workspace_id, f'%"run_id": "{run_id}"%'),
            ).fetchall()
            for claim_row in claim_rows:
                claim = self._decode(claim_row)
                claim["released_at"] = timestamp
                conn.execute(
                    "UPDATE claims SET status = 'released', payload = ?, updated_at = ? WHERE claim_id = ?",
                    (json.dumps(claim), timestamp, claim_row["claim_id"]),
                )
        return run
