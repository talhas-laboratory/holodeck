from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http import HTTPStatus
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from holodeck.api import API_CONTRACT, API_STABILITY, API_VERSION, DOCUMENTATION_PATH
from holodeck.http_server import create_http_server
from holodeck.service import Handler
from holodeck.store import Store


def _start_server(store: Store):
    handler = type("TestHandler", (Handler,), {"store": store, "runtime_host": "127.0.0.1", "runtime_port": 0})
    server = create_http_server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _request(base: str, path: str, *, method: str = "GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if data is not None:
        headers["Content-Length"] = str(len(data))
    req = Request(base + path, data=data, method=method, headers=headers)
    try:
        with urlopen(req) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        body = error.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body.decode("utf-8", errors="replace")}
        return error.code, parsed


@contextmanager
def live_server(tmp_path):
    store = Store(tmp_path / "contract.db")
    server, thread, base = _start_server(store)
    try:
        yield base, store
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_contract_config_exposes_api_version_marker(tmp_path):
    with live_server(tmp_path) as (base, _store):
        status, payload = _request(base, "/api/config")
        assert status == HTTPStatus.OK
        api = payload["api"]
        assert api["version"] == API_VERSION
        assert api["stability"] == API_STABILITY
        assert api["contract"] == API_CONTRACT
        assert api["documentation"] == DOCUMENTATION_PATH
        assert api["max_json_body_bytes"] == 65_536
        assert "breaking_change_policy" in api
        assert payload["policy_enforcement"] == "advisory"


def test_contract_health_endpoint(tmp_path):
    with live_server(tmp_path) as (base, _store):
        status, payload = _request(base, "/health")
        assert status == HTTPStatus.OK
        assert payload == {"status": "ok"}


def test_contract_workspace_lifecycle(tmp_path):
    with live_server(tmp_path) as (base, _store):
        status, workspace = _request(
            base,
            "/api/workspaces",
            method="POST",
            payload={"workspace_id": "demo", "goal": "Ship", "artifact_roots": ["src"]},
        )
        assert status == HTTPStatus.CREATED
        assert workspace["workspace_id"] == "demo"
        assert workspace["artifact_roots"] == ["src"]

        status, listed = _request(base, "/api/workspaces")
        assert status == HTTPStatus.OK
        assert listed["workspaces"][0]["workspace_id"] == "demo"

        status, fetched = _request(base, "/api/workspaces/demo")
        assert status == HTTPStatus.OK
        assert fetched["workspace_id"] == "demo"

        status, updated = _request(
            base,
            "/api/workspaces/demo",
            method="PATCH",
            payload={"scope_out": ["vendor"]},
        )
        assert status == HTTPStatus.OK
        assert updated["scope_out"] == ["vendor"]

        status, payload = _request(base, "/api/workspaces/missing")
        assert status == HTTPStatus.NOT_FOUND
        assert "workspace not found" in payload["error"]

        status, payload = _request(base, "/api/workspaces", method="POST", payload={"workspace_id": "demo"})
        assert status == HTTPStatus.CONFLICT
        assert "already exists" in payload["error"]


def test_contract_task_lifecycle_and_validation(tmp_path):
    with live_server(tmp_path) as (base, _store):
        _request(base, "/api/workspaces", method="POST", payload={"workspace_id": "demo"})

        status, task = _request(
            base,
            "/api/workspaces/demo/tasks",
            method="POST",
            payload={"task_id": "HD-001", "title": "Build API", "status": "ready"},
        )
        assert status == HTTPStatus.CREATED
        assert task["task_id"] == "HD-001"

        status, listed = _request(base, "/api/workspaces/demo/tasks")
        assert status == HTTPStatus.OK
        assert listed["tasks"][0]["title"] == "Build API"

        status, updated = _request(
            base,
            "/api/workspaces/demo/tasks/HD-001",
            method="PATCH",
            payload={"status": "in-progress"},
        )
        assert status == HTTPStatus.OK
        assert updated["status"] == "in-progress"

        status, payload = _request(
            base,
            "/api/workspaces/demo/tasks/HD-001",
            method="PATCH",
            payload={"status": "done"},
        )
        assert status == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "illegal task transition" in payload["error"]

        status, payload = _request(base, "/api/workspaces/demo/tasks/HD-001", method="PATCH", payload={"title": 42})
        assert status == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "title must be a string" in payload["error"]


def test_contract_run_claim_and_complete_lifecycle(tmp_path):
    with live_server(tmp_path) as (base, _store):
        _request(base, "/api/workspaces", method="POST", payload={"workspace_id": "demo"})
        task = _request(
            base,
            "/api/workspaces/demo/tasks",
            method="POST",
            payload={"title": "Claim paths", "status": "ready"},
        )[1]

        status, run = _request(
            base,
            "/api/workspaces/demo/runs",
            method="POST",
            payload={"task_id": task["task_id"], "agent_id": "codex", "claimed_paths": ["src"]},
        )
        assert status == HTTPStatus.CREATED
        assert run["status"] == "active"
        assert run["claimed_paths"] == ["src"]

        status, payload = _request(
            base,
            "/api/workspaces/demo/runs",
            method="POST",
            payload={"task_id": task["task_id"], "claimed_paths": ["src/api.py"]},
        )
        assert status == HTTPStatus.CONFLICT
        assert "overlaps active work" in payload["error"]

        status, claims = _request(base, "/api/workspaces/demo/claims")
        assert status == HTTPStatus.OK
        assert claims["claims"][0]["status"] == "active"

        status, runs = _request(base, "/api/workspaces/demo/runs")
        assert status == HTTPStatus.OK
        assert runs["runs"][0]["run_id"] == run["run_id"]

        status, completed = _request(
            base,
            f"/api/workspaces/demo/runs/{run['run_id']}/complete",
            method="POST",
            payload={"summary": "Done"},
        )
        assert status == HTTPStatus.OK
        assert completed["status"] == "completed"

        status, payload = _request(
            base,
            f"/api/workspaces/demo/runs/{run['run_id']}/complete",
            method="POST",
            payload={},
        )
        assert status == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "already completed" in payload["error"]

        status, claims = _request(base, "/api/workspaces/demo/claims")
        assert claims["claims"][0]["status"] == "released"


def test_contract_invalid_identifier_returns_422(tmp_path):
    with live_server(tmp_path) as (base, _store):
        status, payload = _request(base, "/api/workspaces/not%20valid")
        assert status == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "invalid workspace_id" in payload["error"]


def test_contract_run_requires_terminal_task(tmp_path):
    with live_server(tmp_path) as (base, _store):
        _request(base, "/api/workspaces", method="POST", payload={"workspace_id": "demo"})
        task = _request(
            base,
            "/api/workspaces/demo/tasks",
            method="POST",
            payload={"title": "Done task", "status": "done"},
        )[1]
        status, payload = _request(
            base,
            "/api/workspaces/demo/runs",
            method="POST",
            payload={"task_id": task["task_id"], "claimed_paths": ["src"]},
        )
        assert status == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "cannot begin run" in payload["error"]


def test_contract_missing_run_returns_404(tmp_path):
    with live_server(tmp_path) as (base, _store):
        _request(base, "/api/workspaces", method="POST", payload={"workspace_id": "demo"})
        status, payload = _request(
            base,
            "/api/workspaces/demo/runs/run-missing/complete",
            method="POST",
            payload={},
        )
        assert status == HTTPStatus.NOT_FOUND
        assert "run not found" in payload["error"]


def test_contract_maps_contention_to_503(tmp_path, monkeypatch):
    with live_server(tmp_path) as (base, store):
        def raise_contention(*_args, **_kwargs):
            from holodeck.errors import ContentionError

            raise ContentionError("database is busy")

        monkeypatch.setattr(store, "catalog", raise_contention)
        status, payload = _request(base, "/api/workspaces")
        assert status == HTTPStatus.SERVICE_UNAVAILABLE
        assert "busy" in payload["error"]


def test_contract_documentation_file_exists():
    from pathlib import Path

    assert Path(DOCUMENTATION_PATH).is_file()


def test_contract_rejects_invalid_json_body(tmp_path):
    import socket

    with live_server(tmp_path) as (base, _store):
        host = "127.0.0.1"
        port = int(base.rsplit(":", 1)[-1])
        request = (
            f"POST /api/workspaces HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: 8\r\n"
            "\r\n"
            "{notjson"
        ).encode("ascii")
        with socket.create_connection((host, port), timeout=5) as sock:
            sock.sendall(request)
            response = sock.recv(4096).decode("ascii", errors="replace")
        assert "400" in response.split("\r\n", 1)[0]
