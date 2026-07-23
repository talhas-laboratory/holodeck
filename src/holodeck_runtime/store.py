from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from holodeck_runtime.errors import ConflictError, ContentionError, NotFoundError, ValidationError
from holodeck_runtime.ids import validate_identifier
from holodeck_runtime.lifecycle import (
    validate_run_completion_status,
    validate_run_transition,
    validate_task_can_start_run,
    validate_task_status,
    validate_task_transition,
)
from holodeck_runtime.migrations import configure_connection, migrate
from holodeck_runtime.paths import format_path, normalize_path, paths_intersect, validate_claim_path


def now() -> str:
    return datetime.now(UTC).isoformat()


def _raise_contention(error: sqlite3.OperationalError) -> None:
    message = str(error).lower()
    if error.sqlite_errorcode == sqlite3.SQLITE_BUSY or "locked" in message or "busy" in message:
        raise ContentionError("database is busy") from error
    raise error


def _raise_integrity(error: sqlite3.IntegrityError) -> None:
    message = str(error)
    if "workspaces.workspace_id" in message:
        raise ConflictError("workspace already exists") from error
    if "tasks." in message and "task_id" in message:
        raise ConflictError("task already exists in workspace") from error
    raise ConflictError(message) from error


@contextmanager
def _immediate_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as error:
        _raise_contention(error)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


class Store:
    """Small SQLite authority with explicit, portable JSON records."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            migrate(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        configure_connection(conn)
        return conn

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        return dict(json.loads(row["payload"]))

    @staticmethod
    def _path_overlap(left: str, right: str) -> bool:
        return paths_intersect(normalize_path(left), normalize_path(right))

    def _workspace_record(self, conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT payload FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"workspace not found: {workspace_id}")
        return self._decode(row)

    def _normalize_workspace_boundaries(self, artifact_roots: list[str], scope_out: list[str]) -> tuple[list[str], list[str]]:
        roots = [format_path(normalize_path(root)) for root in artifact_roots if str(root).strip()]
        excluded = [format_path(normalize_path(path)) for path in scope_out if str(path).strip()]
        return roots, excluded

    def catalog(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM workspaces ORDER BY created_at DESC").fetchall()
        return [self._decode(row) for row in rows]

    def create_workspace(self, manifest: dict[str, Any]) -> dict[str, Any]:
        workspace_id = validate_identifier(str(manifest.get("workspace_id", "")), "workspace_id")
        if "artifact_roots" in manifest:
            raw_roots = [str(value) for value in list(manifest.get("artifact_roots") or []) if str(value).strip()]
        else:
            raw_roots = ["."]
        raw_scope_out = [str(value) for value in list(manifest.get("scope_out", []) or []) if str(value).strip()]
        artifact_roots, scope_out = self._normalize_workspace_boundaries(raw_roots, raw_scope_out)
        timestamp = now()
        payload = {
            "workspace_id": workspace_id,
            "label": str(manifest.get("label") or workspace_id),
            "goal": str(manifest.get("goal", "")),
            "purpose": str(manifest.get("purpose", "")),
            "artifact_roots": artifact_roots,
            "scope_out": scope_out,
            "status": "active",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO workspaces VALUES (?, ?, ?, ?)",
                    (workspace_id, json.dumps(payload), timestamp, timestamp),
                )
                conn.commit()
            except sqlite3.IntegrityError as error:
                _raise_integrity(error)
        return payload

    def workspace(self, workspace_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            return self._workspace_record(conn, workspace_id)

    def update_workspace(self, workspace_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            current = self._workspace_record(conn, workspace_id)
            for field in ("label", "goal", "purpose"):
                if field in changes:
                    current[field] = str(changes[field])
            if "artifact_roots" in changes:
                artifact_roots = [str(value) for value in list(changes["artifact_roots"] or []) if str(value).strip()]
            else:
                current_roots = current.get("artifact_roots")
                artifact_roots = ["."] if current_roots is None else [str(value) for value in list(current_roots)]
            if "scope_out" in changes:
                scope_out = [str(value) for value in list(changes["scope_out"] or []) if str(value).strip()]
            else:
                scope_out = [str(value) for value in list(current.get("scope_out", []) or [])]
            current["artifact_roots"], current["scope_out"] = self._normalize_workspace_boundaries(artifact_roots, scope_out)
            current["updated_at"] = now()
            conn.execute(
                "UPDATE workspaces SET payload = ?, updated_at = ? WHERE workspace_id = ?",
                (json.dumps(current), current["updated_at"], workspace_id),
            )
            conn.commit()
        return current

    def tasks(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._workspace_record(conn, workspace_id)
            rows = conn.execute(
                "SELECT payload FROM tasks WHERE workspace_id = ? ORDER BY created_at",
                (workspace_id,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def create_task(self, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            self._workspace_record(conn, workspace_id)
            title = str(payload.get("title", "")).strip()
            if not title:
                raise ValidationError("title is required")
            timestamp = now()
            status = validate_task_status(str(payload.get("status") or "backlog"))
            if payload.get("task_id"):
                task_id = validate_identifier(str(payload["task_id"]), "task_id")
            else:
                task_id = f"task-{uuid.uuid4().hex[:12]}"
            task = {
                "task_id": task_id,
                "workspace_id": workspace_id,
                "title": title,
                "status": status,
                "acceptance_criteria": list(payload.get("acceptance_criteria", []) or []),
                "constraints": list(payload.get("constraints", []) or []),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            try:
                conn.execute(
                    "INSERT INTO tasks(workspace_id, task_id, status, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (workspace_id, task["task_id"], status, json.dumps(task), timestamp, timestamp),
                )
                conn.commit()
            except sqlite3.IntegrityError as error:
                _raise_integrity(error)
        return task

    def task(self, workspace_id: str, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM tasks WHERE workspace_id = ? AND task_id = ?",
                (workspace_id, task_id),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"task not found: {task_id}")
        return self._decode(row)

    def update_task(self, workspace_id: str, task_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        task = self.task(workspace_id, task_id)
        if "title" in changes:
            title = str(changes["title"]).strip()
            if not title:
                raise ValidationError("title is required")
            task["title"] = title
        if "status" in changes:
            validate_task_transition(task["status"], str(changes["status"]))
            task["status"] = validate_task_status(str(changes["status"]))
        for field in ("acceptance_criteria", "constraints"):
            if field in changes:
                task[field] = [str(value) for value in list(changes[field] or []) if str(value).strip()]
        task["updated_at"] = now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET payload = ?, status = ?, updated_at = ? WHERE workspace_id = ? AND task_id = ?",
                (json.dumps(task), task["status"], task["updated_at"], workspace_id, task_id),
            )
            conn.commit()
        return task

    def begin_run(self, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValidationError("task_id is required")

        conn = self._connect()
        try:
            with _immediate_transaction(conn):
                workspace = self._workspace_record(conn, workspace_id)
                task_row = conn.execute(
                    "SELECT payload, status FROM tasks WHERE workspace_id = ? AND task_id = ?",
                    (workspace_id, task_id),
                ).fetchone()
                if task_row is None:
                    raise ValidationError("task_id must identify a task in this workspace")
                validate_task_can_start_run(task_row["status"])

                roots = workspace.get("artifact_roots")
                artifact_roots = ["."] if roots is None else [str(value) for value in list(roots)]
                scope_out = [str(value) for value in list(workspace.get("scope_out", []) or [])]
                raw_paths = [str(path).strip() for path in list(payload.get("claimed_paths", []) or []) if str(path).strip()]
                paths = [validate_claim_path(path, artifact_roots=artifact_roots, scope_out=scope_out) for path in raw_paths]

                active = conn.execute(
                    "SELECT path FROM claims WHERE workspace_id = ? AND status = 'active'",
                    (workspace_id,),
                ).fetchall()
                for path in paths:
                    if any(self._path_overlap(path, row["path"]) for row in active):
                        raise ConflictError(f"claimed path overlaps active work: {path}")
                    for other in paths:
                        if other != path and self._path_overlap(path, other):
                            raise ConflictError(f"claimed paths overlap each other: {path}")

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
                try:
                    conn.execute(
                        "INSERT INTO runs(run_id, workspace_id, task_id, status, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (run["run_id"], workspace_id, task_id, "active", json.dumps(run), timestamp, timestamp),
                    )
                    for path in paths:
                        claim = {
                            "claim_id": f"claim-{uuid.uuid4().hex[:12]}",
                            "workspace_id": workspace_id,
                            "task_id": task_id,
                            "run_id": run["run_id"],
                            "agent_id": run["agent_id"],
                            "path": path,
                        }
                        conn.execute(
                            """
                            INSERT INTO claims(
                                claim_id, workspace_id, task_id, run_id, path, status, payload, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
                            """,
                            (
                                claim["claim_id"],
                                workspace_id,
                                task_id,
                                run["run_id"],
                                path,
                                json.dumps(claim),
                                timestamp,
                                timestamp,
                            ),
                        )
                except sqlite3.IntegrityError as error:
                    _raise_integrity(error)
        except sqlite3.OperationalError as error:
            _raise_contention(error)
        finally:
            conn.close()
        return run

    def runs(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._workspace_record(conn, workspace_id)
            rows = conn.execute(
                "SELECT payload FROM runs WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def claims(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._workspace_record(conn, workspace_id)
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
        conn = self._connect()
        try:
            with _immediate_transaction(conn):
                row = conn.execute(
                    "SELECT payload, status FROM runs WHERE workspace_id = ? AND run_id = ?",
                    (workspace_id, run_id),
                ).fetchone()
                if row is None:
                    raise NotFoundError(f"run not found: {run_id}")
                run = self._decode(row)
                if row["status"] != "active":
                    raise ValidationError(f"run is already {row['status']}")
                timestamp = now()
                result = dict(payload or {})
                next_status = validate_run_completion_status(str(result.get("status") or "completed"))
                validate_run_transition(row["status"], next_status)
                run.update(
                    {
                        "status": next_status,
                        "summary": str(result.get("summary") or ""),
                        "updated_at": timestamp,
                        "completed_at": timestamp,
                    }
                )
                conn.execute(
                    "UPDATE runs SET payload = ?, status = ?, updated_at = ? WHERE workspace_id = ? AND run_id = ?",
                    (json.dumps(run), next_status, timestamp, workspace_id, run_id),
                )
                claim_rows = conn.execute(
                    "SELECT claim_id, payload FROM claims WHERE run_id = ? AND status = 'active'",
                    (run_id,),
                ).fetchall()
                for claim_row in claim_rows:
                    claim = self._decode(claim_row)
                    claim["released_at"] = timestamp
                    conn.execute(
                        "UPDATE claims SET status = 'released', payload = ?, updated_at = ? WHERE claim_id = ?",
                        (json.dumps(claim), timestamp, claim_row["claim_id"]),
                    )
        except sqlite3.OperationalError as error:
            _raise_contention(error)
        finally:
            conn.close()
        return run
