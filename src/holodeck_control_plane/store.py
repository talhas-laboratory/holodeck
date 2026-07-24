from __future__ import annotations

import json
import hashlib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from holodeck_control_plane.errors import ConflictError, ContentionError, NotFoundError, ValidationError
from holodeck_control_plane.ids import validate_identifier, validate_identifier_input
from holodeck_control_plane.lifecycle import (
    validate_run_completion_status,
    validate_run_transition,
    validate_task_can_start_run,
    validate_task_status,
    validate_task_transition,
)
from holodeck_control_plane.migrations import configure_connection, migrate
from holodeck_control_plane.paths import format_path, normalize_path, paths_intersect, validate_claim_path

from holodeck_control_plane.validation import (
    MAX_CLAIMED_PATHS,
    MAX_SHORT_TEXT_LENGTH,
    MAX_TEXT_FIELD_LENGTH,
    MAX_TITLE_LENGTH,
    validate_string_list,
    validate_text_field,
)


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
    if "claims_active_path" in message or "claims.workspace_id, claims.path" in message:
        raise ConflictError("claimed path overlaps active work") from error
    if "claim workspace/task must match run" in message:
        raise ConflictError("claim must match run workspace and task") from error
    if "FOREIGN KEY constraint failed" in message and "tasks" in message:
        raise ValidationError("workspace does not exist") from error
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
        workspace_id = validate_identifier_input(manifest.get("workspace_id"), "workspace_id")
        if "artifact_roots" in manifest:
            raw_roots = validate_string_list("artifact_roots", manifest.get("artifact_roots"))
        else:
            raw_roots = ["."]
        raw_scope_out = validate_string_list("scope_out", manifest.get("scope_out"))
        artifact_roots, scope_out = self._normalize_workspace_boundaries(raw_roots, raw_scope_out)
        timestamp = now()
        payload = {
            "workspace_id": workspace_id,
            "label": validate_text_field(
                "label",
                manifest.get("label"),
                max_length=MAX_SHORT_TEXT_LENGTH,
                default=workspace_id,
            ),
            "goal": validate_text_field("goal", manifest.get("goal")),
            "purpose": validate_text_field("purpose", manifest.get("purpose")),
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
                    max_length = MAX_SHORT_TEXT_LENGTH if field == "label" else MAX_TEXT_FIELD_LENGTH
                    current[field] = validate_text_field(field, changes[field], max_length=max_length)
            if "artifact_roots" in changes:
                artifact_roots = validate_string_list("artifact_roots", changes["artifact_roots"])
            else:
                current_roots = current.get("artifact_roots")
                artifact_roots = ["."] if current_roots is None else validate_string_list("artifact_roots", current_roots)
            if "scope_out" in changes:
                scope_out = validate_string_list("scope_out", changes["scope_out"])
            else:
                scope_out = validate_string_list("scope_out", current.get("scope_out", []))
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
            title = validate_text_field("title", payload.get("title"), max_length=MAX_TITLE_LENGTH, required=True)
            timestamp = now()
            status = validate_task_status(str(payload.get("status") or "backlog"))
            if payload.get("task_id") is not None:
                task_id = validate_identifier_input(payload["task_id"], "task_id")
            else:
                task_id = f"task-{uuid.uuid4().hex[:12]}"
            task = {
                "task_id": task_id,
                "workspace_id": workspace_id,
                "title": title,
                "status": status,
                "acceptance_criteria": validate_string_list("acceptance_criteria", payload.get("acceptance_criteria")),
                "constraints": validate_string_list("constraints", payload.get("constraints")),
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
        conn = self._connect()
        try:
            with _immediate_transaction(conn):
                self._workspace_record(conn, workspace_id)
                row = conn.execute(
                    "SELECT payload, status FROM tasks WHERE workspace_id = ? AND task_id = ?",
                    (workspace_id, task_id),
                ).fetchone()
                if row is None:
                    raise NotFoundError(f"task not found: {task_id}")
                task = self._decode(row)
                current_status = row["status"]

                if "title" in changes:
                    task["title"] = validate_text_field(
                        "title",
                        changes["title"],
                        max_length=MAX_TITLE_LENGTH,
                        required=True,
                    )
                if "status" in changes:
                    validate_task_transition(current_status, str(changes["status"]))
                    task["status"] = validate_task_status(str(changes["status"]))
                for field in ("acceptance_criteria", "constraints"):
                    if field in changes:
                        task[field] = validate_string_list(field, changes[field])
                task["updated_at"] = now()

                updated = conn.execute(
                    """
                    UPDATE tasks
                    SET payload = ?, status = ?, updated_at = ?
                    WHERE workspace_id = ? AND task_id = ? AND status = ?
                    """,
                    (json.dumps(task), task["status"], task["updated_at"], workspace_id, task_id, current_status),
                )
                if updated.rowcount == 0:
                    raise ConflictError("task was modified concurrently")
        except sqlite3.OperationalError as error:
            _raise_contention(error)
        finally:
            conn.close()
        return task

    def begin_run(self, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = validate_text_field("task_id", payload.get("task_id"), max_length=MAX_SHORT_TEXT_LENGTH, required=True)

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
                artifact_roots = ["."] if roots is None else validate_string_list("artifact_roots", roots)
                scope_out = validate_string_list("scope_out", workspace.get("scope_out", []))
                raw_paths = validate_string_list(
                    "claimed_paths",
                    payload.get("claimed_paths"),
                    max_items=MAX_CLAIMED_PATHS,
                )
                paths: list[str] = []
                for path in raw_paths:
                    normalized = validate_claim_path(path, artifact_roots=artifact_roots, scope_out=scope_out)
                    if any(self._path_overlap(normalized, existing) for existing in paths):
                        raise ConflictError(f"claimed paths overlap each other: {normalized}")
                    paths.append(normalized)

                active = conn.execute(
                    "SELECT path FROM claims WHERE workspace_id = ? AND status = 'active'",
                    (workspace_id,),
                ).fetchall()
                for path in paths:
                    if any(self._path_overlap(path, row["path"]) for row in active):
                        raise ConflictError(f"claimed path overlaps active work: {path}")

                timestamp = now()
                run = {
                    "run_id": f"run-{uuid.uuid4().hex[:12]}",
                    "workspace_id": workspace_id,
                    "task_id": task_id,
                    "agent_id": validate_text_field(
                        "agent_id",
                        payload.get("agent_id"),
                        max_length=MAX_SHORT_TEXT_LENGTH,
                        default="unknown",
                    ),
                    "intent": validate_text_field("intent", payload.get("intent")),
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
                        "summary": validate_text_field("summary", result.get("summary")),
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

    def sources(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._workspace_record(conn, workspace_id)
            rows = conn.execute("SELECT payload FROM workspace_sources WHERE workspace_id = ? ORDER BY created_at", (workspace_id,)).fetchall()
        return [self._decode(row) for row in rows]

    def create_source(self, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        source_id = validate_identifier_input(payload.get("source_id") or f"source-{uuid.uuid4().hex[:12]}", "source_id")
        timestamp = now()
        source = {
            "source_id": source_id,
            "workspace_id": workspace_id,
            "label": validate_text_field("label", payload.get("label"), max_length=MAX_SHORT_TEXT_LENGTH, required=True),
            "content": validate_text_field("content", payload.get("content"), required=True),
            "trust_class": validate_text_field("trust_class", payload.get("trust_class"), max_length=MAX_SHORT_TEXT_LENGTH, default="untrusted_reference"),
            "revision": validate_text_field("revision", payload.get("revision"), max_length=MAX_SHORT_TEXT_LENGTH, default="1"),
            "created_at": timestamp,
        }
        with self._connect() as conn:
            self._workspace_record(conn, workspace_id)
            try:
                conn.execute("INSERT INTO workspace_sources VALUES (?, ?, ?, ?, ?)", (source_id, workspace_id, source["revision"], json.dumps(source), timestamp))
                conn.commit()
            except sqlite3.IntegrityError as error:
                _raise_integrity(error)
        return source

    def propose(self, workspace_id: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        kind = validate_text_field("kind", payload.get("kind"), max_length=MAX_SHORT_TEXT_LENGTH, required=True)
        if kind not in {"delegation_contract", "requirement"}:
            raise ValidationError("unsupported proposal kind")
        source_ids = validate_string_list("source_ids", payload.get("source_ids"), max_items=64)
        if not source_ids:
            raise ValidationError("source_ids is required")
        proposal_body = payload.get("proposal")
        if not isinstance(proposal_body, dict):
            raise ValidationError("proposal must be an object")
        curator = validate_text_field("curator", payload.get("curator"), max_length=MAX_SHORT_TEXT_LENGTH, required=True)
        proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
        timestamp = now()
        proposal = {"proposal_id": proposal_id, "workspace_id": workspace_id, "task_id": task_id, "kind": kind, "status": "proposed", "curator": curator, "source_ids": source_ids, "proposal": proposal_body, "created_at": timestamp}
        conn = self._connect()
        try:
            with _immediate_transaction(conn):
                self.task(workspace_id, task_id)
                found = {row[0] for row in conn.execute("SELECT source_id FROM workspace_sources WHERE workspace_id = ? AND source_id IN (%s)" % ",".join("?" * len(source_ids)), (workspace_id, *source_ids)).fetchall()}
                if found != set(source_ids):
                    raise ValidationError("source_ids must identify sources in this workspace")
                conn.execute("INSERT INTO curator_proposals(proposal_id, workspace_id, task_id, kind, status, payload, created_at) VALUES (?, ?, ?, ?, 'proposed', ?, ?)", (proposal_id, workspace_id, task_id, kind, json.dumps(proposal), timestamp))
        finally:
            conn.close()
        return proposal

    def approve_proposal(self, workspace_id: str, task_id: str, proposal_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            with _immediate_transaction(conn):
                row = conn.execute("SELECT payload, status FROM curator_proposals WHERE proposal_id = ? AND workspace_id = ? AND task_id = ?", (proposal_id, workspace_id, task_id)).fetchone()
                if row is None:
                    raise NotFoundError(f"proposal not found: {proposal_id}")
                if row["status"] != "proposed":
                    raise ValidationError(f"proposal is already {row['status']}")
                proposal = self._decode(row)
                proposal["status"] = "approved"
                proposal["approved_at"] = now()
                conn.execute("UPDATE curator_proposals SET status = 'approved', payload = ?, decided_at = ? WHERE proposal_id = ?", (json.dumps(proposal), proposal["approved_at"], proposal_id))
        finally:
            conn.close()
        return proposal

    def compile_mission(self, workspace_id: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        proposal_ids = validate_string_list("proposal_ids", payload.get("proposal_ids"), max_items=128)
        if not proposal_ids:
            raise ValidationError("proposal_ids is required")
        conn = self._connect()
        try:
            with _immediate_transaction(conn):
                self.task(workspace_id, task_id)
                placeholders = ",".join("?" * len(proposal_ids))
                rows = conn.execute(f"SELECT payload FROM curator_proposals WHERE workspace_id = ? AND task_id = ? AND status = 'approved' AND proposal_id IN ({placeholders})", (workspace_id, task_id, *proposal_ids)).fetchall()
                proposals = [self._decode(row) for row in rows]
                if len(proposals) != len(proposal_ids):
                    raise ValidationError("proposal_ids must identify approved proposals for this task")
                contracts = [item for item in proposals if item["kind"] == "delegation_contract"]
                requirements = [item for item in proposals if item["kind"] == "requirement"]
                if len(contracts) != 1 or not requirements:
                    raise ValidationError("mission requires one delegation_contract and at least one requirement")
                timestamp = now()
                packet = {"workspace_id": workspace_id, "task_id": task_id, "delegation_contract": contracts[0], "requirements": requirements, "compiled_at": timestamp, "compiler_version": "1"}
                packet_hash = hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                mission_id = f"mission-{uuid.uuid4().hex[:12]}"
                mission = {"mission_id": mission_id, "status": "ready", "packet_hash": packet_hash, **packet}
                conn.execute("INSERT INTO missions VALUES (?, ?, ?, 'ready', ?, ?, ?)", (mission_id, workspace_id, task_id, packet_hash, json.dumps(mission), timestamp))
        finally:
            conn.close()
        return mission

    def mission(self, workspace_id: str, task_id: str, mission_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM missions WHERE mission_id = ? AND workspace_id = ? AND task_id = ?", (mission_id, workspace_id, task_id)).fetchone()
        if row is None:
            raise NotFoundError(f"mission not found: {mission_id}")
        return self._decode(row)

    def missions(self, workspace_id: str, task_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self.task(workspace_id, task_id)
            rows = conn.execute("SELECT payload FROM missions WHERE workspace_id = ? AND task_id = ? ORDER BY created_at DESC", (workspace_id, task_id)).fetchall()
        return [self._decode(row) for row in rows]

    def add_evidence(self, workspace_id: str, task_id: str, mission_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        mission = self.mission(workspace_id, task_id, mission_id)
        if mission["status"] != "ready":
            raise ValidationError(f"mission is already {mission['status']}")
        requirement_id = validate_text_field("requirement_id", payload.get("requirement_id"), max_length=MAX_SHORT_TEXT_LENGTH, required=True)
        valid = {item["proposal_id"] for item in mission["requirements"]}
        if requirement_id not in valid:
            raise ValidationError("requirement_id is not in this mission")
        timestamp = now()
        evidence = {"evidence_id": f"evidence-{uuid.uuid4().hex[:12]}", "mission_id": mission_id, "requirement_id": requirement_id, "artifact": validate_text_field("artifact", payload.get("artifact"), required=True), "created_at": timestamp}
        with self._connect() as conn:
            conn.execute("INSERT INTO mission_evidence VALUES (?, ?, ?, ?, ?)", (evidence["evidence_id"], mission_id, requirement_id, json.dumps(evidence), timestamp))
            conn.commit()
        return evidence

    def accept_mission(self, workspace_id: str, task_id: str, mission_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            with _immediate_transaction(conn):
                mission = self.mission(workspace_id, task_id, mission_id)
                if mission["status"] != "ready":
                    raise ValidationError(f"mission is already {mission['status']}")
                evidence_ids = {row[0] for row in conn.execute("SELECT DISTINCT requirement_id FROM mission_evidence WHERE mission_id = ?", (mission_id,)).fetchall()}
                required = {item["proposal_id"] for item in mission["requirements"]}
                if not required.issubset(evidence_ids):
                    raise ValidationError("mission requires evidence for every requirement")
                timestamp = now()
                decision = {"decision_id": f"decision-{uuid.uuid4().hex[:12]}", "mission_id": mission_id, "decision": "accepted", "created_at": timestamp}
                mission["status"] = "accepted"
                mission["accepted_at"] = timestamp
                conn.execute("UPDATE missions SET status = 'accepted', payload = ? WHERE mission_id = ?", (json.dumps(mission), mission_id))
                conn.execute("INSERT INTO acceptance_decisions VALUES (?, ?, 'accepted', ?, ?)", (decision["decision_id"], mission_id, json.dumps(decision), timestamp))
        finally:
            conn.close()
        return decision
