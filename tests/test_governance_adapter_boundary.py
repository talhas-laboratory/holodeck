"""HTTP/CLI adapter boundary tests for M1 governance commands."""

from __future__ import annotations

import ast
import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from holodeck_control_plane.governance_commands import governance_mutation_entrypoints
from holodeck_control_plane.http_server import create_http_server
from holodeck_control_plane.service import Handler
from holodeck_control_plane.store import Store
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.testing.seed import seed_authorized_task_world


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"


def _request(base: str, path: str, *, method: str = "GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = Request(base + path, data=data, method=method, headers=headers)
    try:
        with urlopen(req) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        body = error.read().decode()
        return error.code, json.loads(body) if body else {"error": str(error)}


def test_http_governance_command_and_reconstruction(tmp_path) -> None:
    db = tmp_path / "runtime.db"
    store = Store(db)
    conn = __import__("sqlite3").connect(db)
    conn.row_factory = __import__("sqlite3").Row
    world = seed_authorized_task_world(conn)
    conn.close()
    handler = type(
        "TestHandler",
        (Handler,),
        {"store": store, "runtime_host": "127.0.0.1", "runtime_port": 0},
    )
    server = create_http_server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    command_id = generate_uuidv7()
    try:
        config = _request(base, "/api/config")[1]
        assert any(
            item["id"] == "governance_commands" for item in config["capabilities"]
        )
        status, body = _request(
            base,
            "/api/governance/commands",
            method="POST",
            payload={
                "command": {
                    "command_id": command_id,
                    "command_type": "task.transition",
                    "tenant_id": world["tenant_id"],
                    "actor_id": world["actor_id"],
                    "target_object_id": world["task_object_id"],
                    "expected_revision": 1,
                    "idempotency_key": "http-gov-1",
                    "payload_schema_version": "m1.command.task_transition.v1",
                    "correlation_id": generate_uuidv7(),
                    "issued_at": datetime(2026, 7, 24, 12, 0, tzinfo=UTC).isoformat(),
                    "payload": {"to_state": "ready"},
                },
            },
        )
        assert status == 201, body
        assert body["receipt"]["outcome"] == "accepted"
        recon_status, recon = _request(
            base,
            f"/api/governance/commands/{command_id}/reconstruction?tenant_id={world['tenant_id']}",
        )
        assert recon_status == 200
        assert recon["receipt"]["outcome"] == "accepted"
        assert recon["evaluation_result"] is not None
        # Caller-supplied authority fields are rejected
        bad_status, bad = _request(
            base,
            "/api/governance/commands",
            method="POST",
            payload={
                "actor_permitted": True,
                "command": {
                    "command_id": generate_uuidv7(),
                    "command_type": "task.transition",
                    "tenant_id": world["tenant_id"],
                    "actor_id": world["actor_id"],
                    "target_object_id": world["task_object_id"],
                    "expected_revision": 2,
                    "idempotency_key": "http-gov-bad",
                    "payload_schema_version": "m1.command.task_transition.v1",
                    "correlation_id": generate_uuidv7(),
                    "issued_at": datetime(2026, 7, 24, 12, 0, tzinfo=UTC).isoformat(),
                    "payload": {"to_state": "active"},
                },
            },
        )
        assert bad_status == 422
        assert "caller-supplied" in bad["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cli_governance_command(tmp_path) -> None:
    from holodeck_control_plane.cli import main
    from holodeck_control_plane.governance_commands import (
        load_governance_command_json,
        reconstruct_governance_decision,
        submit_governance_command_request,
    )

    db = tmp_path / "cli.db"
    request_path = tmp_path / "req.json"
    conn = __import__("sqlite3").connect(db)
    conn.row_factory = __import__("sqlite3").Row
    world = seed_authorized_task_world(conn)
    conn.close()
    command_id = generate_uuidv7()
    request_path.write_text(
        json.dumps(
            {
                "command": {
                    "command_id": command_id,
                    "command_type": "task.transition",
                    "tenant_id": world["tenant_id"],
                    "actor_id": world["actor_id"],
                    "target_object_id": world["task_object_id"],
                    "expected_revision": 1,
                    "idempotency_key": "cli-gov-1",
                    "payload_schema_version": "m1.command.task_transition.v1",
                    "correlation_id": generate_uuidv7(),
                    "issued_at": datetime(2026, 7, 24, 12, 0, tzinfo=UTC).isoformat(),
                    "payload": {"to_state": "ready"},
                },
            }
        ),
        encoding="utf-8",
    )
    payload = submit_governance_command_request(
        str(db), load_governance_command_json(str(request_path))
    )
    assert payload["receipt"]["outcome"] == "accepted"
    reconstructed = reconstruct_governance_decision(
        str(db), tenant_id=world["tenant_id"], command_id=command_id
    )
    assert reconstructed["evaluation_result"] is not None
    import pytest

    with pytest.raises(SystemExit) as exited:
        import sys as _sys

        _sys.argv = ["holodeck", "governance-command", "--help"]
        main()
    assert exited.value.code == 0


def test_adapters_do_not_write_gov_tables_directly() -> None:
    assert governance_mutation_entrypoints() == (
        "holodeck_control_plane.governance_commands.submit_governance_command",
    )
    store_src = (SRC_ROOT / "holodeck_control_plane" / "store.py").read_text(
        encoding="utf-8"
    )
    assert "gov_" not in store_src
    for relative in ("service.py", "cli.py", "mcp_server.py"):
        path = SRC_ROOT / "holodeck_control_plane" / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
        assert "holodeck_governance.storage.sqlite.command_service" not in imported
