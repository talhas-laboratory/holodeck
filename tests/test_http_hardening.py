from __future__ import annotations

import json
import threading
from http import HTTPStatus
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from holodeck_control_plane.http_request import MAX_BODY_BYTES, validate_bind_host
from holodeck_control_plane.http_server import create_http_server
from holodeck_control_plane.service import Handler
from holodeck_control_plane.store import Store


def _start_server(store: Store, **server_kwargs):
    handler = type("TestHandler", (Handler,), {"store": store, "runtime_host": "127.0.0.1", "runtime_port": 0})
    server = create_http_server(("127.0.0.1", 0), handler, **server_kwargs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _request(base: str, path: str, *, method: str = "GET", payload=None, headers: dict[str, str] | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request_headers = dict(headers or {})
    if payload is not None and "Content-Type" not in request_headers:
        request_headers["Content-Type"] = "application/json"
    if data is not None:
        request_headers["Content-Length"] = str(len(data))
    req = Request(base + path, data=data, method=method, headers=request_headers)
    try:
        with urlopen(req) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        body = error.read()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"error": body.decode("utf-8", errors="replace")}
        return error.code, payload


def test_http_maps_not_found_to_404(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)
    try:
        status, payload = _request(base, "/api/workspaces/missing")
        assert status == HTTPStatus.NOT_FOUND
        assert "workspace not found" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_maps_conflict_to_409(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    server, thread, base = _start_server(store)
    try:
        status, payload = _request(base, "/api/workspaces", method="POST", payload={"workspace_id": "demo"})
        assert status == HTTPStatus.CONFLICT
        assert "already exists" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_maps_duplicate_task_to_409(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    store.create_task("demo", {"task_id": "HD-001", "title": "First"})
    server, thread, base = _start_server(store)
    try:
        status, payload = _request(
            base,
            "/api/workspaces/demo/tasks",
            method="POST",
            payload={"task_id": "HD-001", "title": "Duplicate"},
        )
        assert status == HTTPStatus.CONFLICT
        assert "task already exists" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_maps_validation_error_to_422(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)
    try:
        status, payload = _request(
            base,
            "/api/workspaces",
            method="POST",
            payload={"workspace_id": "demo", "goal": "Ship"},
        )
        assert status == HTTPStatus.CREATED
        status, payload = _request(
            base,
            "/api/workspaces/demo/tasks",
            method="POST",
            payload={"title": "No status path", "status": "done"},
        )
        assert status == HTTPStatus.CREATED
        status, payload = _request(
            base,
            f"/api/workspaces/demo/runs",
            method="POST",
            payload={"task_id": payload["task_id"], "claimed_paths": ["src"]},
        )
        assert status == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "cannot begin run" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_rejects_invalid_json_with_400(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)
    try:
        req = Request(
            base + "/api/workspaces",
            data=b"{notjson",
            method="POST",
            headers={"Content-Type": "application/json", "Content-Length": "8"},
        )
        with pytest.raises(HTTPError) as error:
            urlopen(req)
        assert error.value.code == HTTPStatus.BAD_REQUEST
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_rejects_unsupported_media_type_with_415(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)
    try:
        req = Request(
            base + "/api/workspaces",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "text/plain", "Content-Length": "2"},
        )
        with pytest.raises(HTTPError) as error:
            urlopen(req)
        assert error.value.code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_rejects_non_object_json_with_400(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)
    try:
        req = Request(
            base + "/api/workspaces",
            data=b"[]",
            method="POST",
            headers={"Content-Type": "application/json", "Content-Length": "2"},
        )
        with pytest.raises(HTTPError) as error:
            urlopen(req)
        assert error.value.code == HTTPStatus.BAD_REQUEST
        assert "object" in error.value.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_rejects_invalid_workspace_identifier_with_422(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)
    try:
        status, payload = _request(base, "/api/workspaces/not%20valid")
        assert status == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "invalid workspace_id" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_non_loopback_bind_requires_insecure_opt_in():
    with pytest.raises(SystemExit, match="refusing non-loopback bind"):
        validate_bind_host("0.0.0.0", insecure_bind=False)
    assert validate_bind_host("0.0.0.0", insecure_bind=True) == "0.0.0.0"


def test_loopback_hosts_are_allowed_without_insecure_bind():
    assert validate_bind_host("127.0.0.1", insecure_bind=False) == "127.0.0.1"
    assert validate_bind_host("localhost", insecure_bind=False) == "localhost"


def test_http_rejects_oversized_body_with_413(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)
    try:
        req = Request(
            base + "/api/workspaces",
            data=b"{}",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(MAX_BODY_BYTES + 1),
            },
        )
        with pytest.raises(HTTPError) as error:
            urlopen(req)
        assert error.value.code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_rejects_invalid_content_length_with_400(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)
    try:
        req = Request(
            base + "/api/workspaces",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json", "Content-Length": "not-a-number"},
        )
        with pytest.raises(HTTPError) as error:
            urlopen(req)
        assert error.value.code == HTTPStatus.BAD_REQUEST
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_rejects_missing_content_length_with_400(tmp_path):
    import socket

    store = Store(tmp_path / "runtime.db")
    server, thread, _base = _start_server(store)
    host = "127.0.0.1"
    port = server.server_port
    try:
        request = (
            f"POST /api/workspaces HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
        ).encode("ascii")
        with socket.create_connection((host, port), timeout=5) as sock:
            sock.sendall(request)
            response = sock.recv(4096).decode("ascii", errors="replace")
        status_line = response.split("\r\n", 1)[0]
        assert "400" in status_line
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_maps_contention_to_503(tmp_path, monkeypatch):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_server(store)

    def raise_contention(*_args, **_kwargs):
        from holodeck_control_plane.errors import ContentionError

        raise ContentionError("database is busy")

    monkeypatch.setattr(store, "create_workspace", raise_contention)
    try:
        status, payload = _request(base, "/api/workspaces", method="POST", payload={"workspace_id": "demo"})
        assert status == HTTPStatus.SERVICE_UNAVAILABLE
        assert "busy" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_returns_503_when_at_capacity(tmp_path):
    store = Store(tmp_path / "runtime.db")
    started = threading.Event()
    release = threading.Event()

    class BlockingHandler(Handler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") == "/block":
                started.set()
                release.wait(timeout=5)
                self.send_response(HTTPStatus.OK)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            return super().do_GET()

    handler = type(
        "CapacityHandler",
        (BlockingHandler,),
        {"store": store, "runtime_host": "127.0.0.1", "runtime_port": 0},
    )
    server = create_http_server(("127.0.0.1", 0), handler, max_concurrent_requests=1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def block():
        req = Request(base + "/block")
        with urlopen(req, timeout=10):
            return

    blocker = threading.Thread(target=block, daemon=True)
    blocker.start()
    assert started.wait(timeout=5)

    try:
        req = Request(base + "/health")
        with pytest.raises(HTTPError) as error:
            urlopen(req, timeout=5)
        assert error.value.code == HTTPStatus.SERVICE_UNAVAILABLE
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        blocker.join(timeout=2)
