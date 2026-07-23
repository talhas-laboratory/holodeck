from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from holodeck_runtime.errors import ConflictError, ContentionError, ValidationError
from holodeck_runtime.lifecycle import validate_task_transition
from holodeck_runtime.migrations import configure_connection, migrate
from holodeck_runtime.paths import format_path, normalize_path, validate_claim_path
from holodeck_runtime.store import Store


def test_concurrent_claims_allow_only_one_active_run(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    task = store.create_task("demo", {"title": "Race", "status": "ready"})
    barrier = threading.Barrier(2)
    results: list = []
    errors: list[BaseException] = []

    def attempt():
        local = Store(tmp_path / "runtime.db")
        try:
            barrier.wait(timeout=5)
            results.append(
                local.begin_run(
                    "demo",
                    {"task_id": task["task_id"], "agent_id": "agent", "claimed_paths": ["src/api.py"]},
                )
            )
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ConflictError)
    assert store.claims("demo")[0]["status"] == "active"


def test_parent_child_paths_conflict(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    task = store.create_task("demo", {"title": "Overlap", "status": "ready"})
    store.begin_run("demo", {"task_id": task["task_id"], "claimed_paths": ["src"]})
    with pytest.raises(ConflictError, match="overlaps active work"):
        store.begin_run("demo", {"task_id": task["task_id"], "claimed_paths": ["src/api.py"]})


def test_legacy_database_upgrades_and_releases_by_run_id(tmp_path):
    database = tmp_path / "legacy.db"
    conn = sqlite3.connect(database)
    conn.executescript(
        """
        CREATE TABLE workspaces (
            workspace_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE claims (
            claim_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    timestamp = "2026-01-01T00:00:00+00:00"
    workspace_payload = json.dumps({"workspace_id": "demo", "artifact_roots": ["."], "scope_out": []})
    task_payload = json.dumps({"task_id": "task-1", "workspace_id": "demo", "title": "Legacy", "status": "ready"})
    run_payload = json.dumps(
        {
            "run_id": "run-legacy",
            "workspace_id": "demo",
            "task_id": "task-1",
            "status": "active",
            "claimed_paths": ["src"],
        }
    )
    claim_payload = json.dumps(
        {
            "claim_id": "claim-legacy",
            "workspace_id": "demo",
            "task_id": "task-1",
            "run_id": "run-legacy",
            "path": "src",
        }
    )
    conn.execute("INSERT INTO workspaces VALUES ('demo', ?, ?, ?)", (workspace_payload, timestamp, timestamp))
    conn.execute("INSERT INTO tasks VALUES ('task-1', 'demo', ?, ?, ?)", (task_payload, timestamp, timestamp))
    conn.execute("INSERT INTO runs VALUES ('run-legacy', 'demo', 'task-1', ?, ?, ?)", (run_payload, timestamp, timestamp))
    conn.execute(
        "INSERT INTO claims VALUES ('claim-legacy', 'demo', 'task-1', 'src', 'active', ?, ?, ?)",
        (claim_payload, timestamp, timestamp),
    )
    conn.commit()
    conn.close()

    store = Store(database)
    completed = store.complete_run("demo", "run-legacy", {"summary": "done"})
    assert completed["status"] == "completed"
    assert store.claims("demo")[0]["status"] == "released"


def test_same_task_id_in_two_workspaces(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "alpha"})
    store.create_workspace({"workspace_id": "beta"})
    alpha = store.create_task("alpha", {"task_id": "HD-1", "title": "Alpha task"})
    beta = store.create_task("beta", {"task_id": "HD-1", "title": "Beta task"})
    assert alpha["task_id"] == beta["task_id"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (".", "."),
        ("src/", "src"),
        ("src/api.py", "src/api.py"),
    ],
)
def test_path_normalization(raw, expected):
    assert format_path(normalize_path(raw)) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "/abs", "src\\api.py", "src/../secret", "..", "C:/Users/x", "C:\\Users\\x"],
)
def test_invalid_paths_are_rejected(raw):
    with pytest.raises(ValidationError):
        normalize_path(raw)


def test_scope_out_rejects_ancestor_and_descendant_claims(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo", "artifact_roots": ["."], "scope_out": ["src/vendor"]})
    task = store.create_task("demo", {"title": "Boundary", "status": "ready"})
    for path in ("src", "src/vendor", "src/vendor/foo"):
        with pytest.raises(ValidationError, match="scope_out"):
            store.begin_run("demo", {"task_id": task["task_id"], "claimed_paths": [path]})


def test_claim_must_fall_under_artifact_root(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo", "artifact_roots": ["src"]})
    task = store.create_task("demo", {"title": "Rooted", "status": "ready"})
    with pytest.raises(ValidationError, match="artifact roots"):
        store.begin_run("demo", {"task_id": task["task_id"], "claimed_paths": ["tests/a.py"]})


def test_task_lifecycle_rejects_illegal_transition(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    task = store.create_task("demo", {"title": "Lifecycle", "status": "backlog"})
    with pytest.raises(ValidationError, match="illegal task transition"):
        store.update_task("demo", task["task_id"], {"status": "done"})


def test_run_cannot_start_for_done_task(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    task = store.create_task("demo", {"title": "Done", "status": "done"})
    with pytest.raises(ValidationError, match="cannot begin run"):
        store.begin_run("demo", {"task_id": task["task_id"], "claimed_paths": ["src"]})


def test_complete_run_rejects_second_completion(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    task = store.create_task("demo", {"title": "Complete once", "status": "ready"})
    run = store.begin_run("demo", {"task_id": task["task_id"], "claimed_paths": ["src"]})
    store.complete_run("demo", run["run_id"])
    with pytest.raises(ValidationError, match="already completed"):
        store.complete_run("demo", run["run_id"])


def test_task_transition_matrix_allows_documented_edges():
    validate_task_transition("backlog", "ready")
    validate_task_transition("review", "done")
    with pytest.raises(ValidationError):
        validate_task_transition("done", "ready")


def test_validate_claim_path_table():
    assert validate_claim_path("src/a.py", artifact_roots=["."], scope_out=[]) == "src/a.py"
    with pytest.raises(ValidationError):
        validate_claim_path("src/a.py", artifact_roots=["docs"], scope_out=[])


def test_migrate_is_idempotent(tmp_path):
    database = tmp_path / "runtime.db"
    store = Store(database)
    store.create_workspace({"workspace_id": "demo"})
    conn = sqlite3.connect(database)
    configure_connection(conn)
    migrate(conn)
    versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
    conn.close()
    assert versions == [1]


def test_legacy_invalid_status_is_coerced_without_data_loss(tmp_path):
    database = tmp_path / "legacy.db"
    conn = sqlite3.connect(database)
    conn.executescript(
        """
        CREATE TABLE workspaces (
            workspace_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE claims (
            claim_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    timestamp = "2026-01-01T00:00:00+00:00"
    conn.execute(
        "INSERT INTO workspaces VALUES ('demo', ?, ?, ?)",
        (json.dumps({"workspace_id": "demo", "artifact_roots": ["."], "scope_out": []}), timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO tasks VALUES ('task-1', 'demo', ?, ?, ?)",
        (json.dumps({"task_id": "task-1", "workspace_id": "demo", "title": "Legacy", "status": "shipped"}), timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO runs VALUES ('run-1', 'demo', 'task-1', ?, ?, ?)",
        (json.dumps({"run_id": "run-1", "workspace_id": "demo", "task_id": "task-1", "status": "weird"}), timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO claims VALUES ('claim-1', 'demo', 'task-1', 'src', 'active', ?, ?, ?)",
        (json.dumps({"claim_id": "claim-1", "run_id": "run-1", "path": "src"}), timestamp, timestamp),
    )
    conn.commit()
    conn.close()

    store = Store(database)
    tasks = store.tasks("demo")
    assert len(tasks) == 1
    assert tasks[0]["status"] == "backlog"
    assert store.runs("demo")[0]["status"] == "active"
    assert store.claims("demo")[0]["status"] == "active"


def test_failed_legacy_migration_rolls_back(tmp_path):
    database = tmp_path / "legacy.db"
    conn = sqlite3.connect(database)
    conn.executescript(
        """
        CREATE TABLE workspaces (
            workspace_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE claims (
            claim_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    timestamp = "2026-01-01T00:00:00+00:00"
    conn.execute(
        "INSERT INTO workspaces VALUES ('demo', ?, ?, ?)",
        (json.dumps({"workspace_id": "demo"}), timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO tasks VALUES ('task-1', 'demo', ?, ?, ?)",
        (json.dumps({"task_id": "task-1", "status": "ready", "title": "Keep"}), timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO claims VALUES ('claim-1', 'demo', 'task-1', 'src', 'active', ?, ?, ?)",
        (json.dumps({"claim_id": "claim-1", "path": "src"}), timestamp, timestamp),
    )
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="missing run_id"):
        Store(database)

    conn = sqlite3.connect(database)
    assert conn.execute("SELECT count(*) FROM tasks").fetchone()[0] == 1
    assert "run_id" not in {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 0
    conn.close()


def test_duplicate_task_raises_conflict(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    store.create_task("demo", {"task_id": "HD-001", "title": "One"})
    with pytest.raises(ConflictError, match="task already exists"):
        store.create_task("demo", {"task_id": "HD-001", "title": "Two"})


def test_empty_artifact_roots_reject_claims(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo", "artifact_roots": []})
    task = store.create_task("demo", {"title": "Blocked", "status": "ready"})
    with pytest.raises(ValidationError, match="artifact roots"):
        store.begin_run("demo", {"task_id": task["task_id"], "claimed_paths": ["src"]})


def test_invalid_workspace_id_is_rejected(tmp_path):
    store = Store(tmp_path / "runtime.db")
    with pytest.raises(ValidationError, match="invalid workspace_id"):
        store.create_workspace({"workspace_id": "not valid"})
