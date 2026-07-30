from __future__ import annotations

import json
import mimetypes
from importlib.resources import files
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable

from .api import api_config_section
from .errors import HolodeckError, ValidationError
from .http_request import http_status_for_error, read_json_object, validate_bind_host, validate_identifier
from .http_server import create_http_server
from .project import DEFAULT_POLICY
from .store import Store


class Handler(BaseHTTPRequestHandler):
    store: Store
    runtime_host = "127.0.0.1"
    runtime_port = 8787

    def log_message(self, *_: object) -> None:
        return

    def _send(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, action: Callable[[], Any]) -> None:
        try:
            result = action()
            if result is not None:
                return result
        except Exception as error:  # noqa: BLE001
            status = http_status_for_error(error)
            message = str(error) if isinstance(error, (HolodeckError, ValueError, json.JSONDecodeError)) else "internal error"
            self._send(status, {"error": message})

    def _json(self) -> dict[str, Any]:
        return read_json_object(self.headers, self.rfile)

    def _workspace_id(self, parts: list[str], index: int) -> str:
        return validate_identifier(parts[index], "workspace_id")

    def _task_id(self, parts: list[str], index: int) -> str:
        return validate_identifier(parts[index], "task_id")

    def _run_id(self, parts: list[str], index: int) -> str:
        return validate_identifier(parts[index], "run_id")

    def _proposal_id(self, parts: list[str], index: int) -> str:
        return validate_identifier(parts[index], "proposal_id")

    def _mission_id(self, parts: list[str], index: int) -> str:
        return validate_identifier(parts[index], "mission_id")

    def _asset(self, name: str) -> None:
        root = files("holodeck_control_plane").joinpath("frontend")
        asset = root.joinpath(name)
        if not asset.is_file():
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
        body = asset.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _documentation(self, slug: str) -> None:
        filenames = {"http-api-v1": "http-api-v1.md", "mcp-setup": "mcp-setup.md"}
        filename = filenames.get(slug)
        if filename is None:
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
        resource = files("holodeck_control_plane").joinpath("docs", filename)
        if not resource.is_file():
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
        body = resource.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parts = [part for part in self.path.split("?")[0].split("/") if part]

        def action() -> None:
            if not parts:
                return self._asset("index.html")
            if len(parts) == 2 and parts[0] == "assets":
                return self._asset(parts[1])
            if len(parts) == 2 and parts[0] == "docs" and parts[1] in {"http-api-v1", "mcp-setup"}:
                return self._documentation(parts[1])
            if parts == ["health"]:
                return self._send(HTTPStatus.OK, {"status": "ok"})
            if parts == ["api", "config"]:
                return self._send(
                    HTTPStatus.OK,
                    {
                        "api": api_config_section(),
                        "runtime": {
                            "host": self.runtime_host,
                            "port": self.runtime_port,
                            "database": self.store.database,
                            "storage": "sqlite",
                            "authority": "local",
                        },
                        "project_manifest": {
                            "schema_version": "1.0",
                            "project_root": ".",
                            "artifact_roots": ["."],
                            "generated_by": "holodeck",
                        },
                        "onboarding_policy": {"schema_version": "1.0", "actions": DEFAULT_POLICY},
                        "policy_enforcement": "advisory",
                        "capabilities": [
                            {"id": "workspaces", "label": "Workspace intent and boundaries", "status": "available"},
                            {"id": "tasks", "label": "Task planning and status", "status": "available"},
                            {"id": "runs", "label": "Agent runs and path claims", "status": "available"},
                            {"id": "overlap", "label": "Overlapping path protection", "status": "available"},
                            {"id": "policy", "label": "Advisory project onboarding policy", "status": "available"},
                            {"id": "governance_commands", "label": "M1 governed command boundary", "status": "available"},
                            {"id": "evidence", "label": "Verification evidence", "status": "planned"},
                            {"id": "handoffs", "label": "Agent handoffs", "status": "planned"},
                            {"id": "adapters", "label": "Repository, agent, and CI adapters", "status": "planned"},
                        ],
                    },
                )
            if len(parts) == 5 and parts[:3] == ["api", "governance", "commands"] and parts[4] == "reconstruction":
                from holodeck_control_plane.governance_commands import (
                    reconstruct_governance_decision,
                )

                command_id = validate_identifier(parts[3], "command_id")
                query = self.path.split("?", 1)
                params = {}
                if len(query) == 2:
                    from urllib.parse import parse_qs

                    params = {k: v[0] for k, v in parse_qs(query[1]).items() if v}
                tenant_id = params.get("tenant_id")
                if not tenant_id:
                    raise ValidationError("tenant_id query parameter is required")
                return self._send(
                    HTTPStatus.OK,
                    reconstruct_governance_decision(
                        self.store.database,
                        tenant_id=tenant_id,
                        command_id=command_id,
                    ),
                )
            if parts == ["api", "workspaces"]:
                return self._send(HTTPStatus.OK, {"workspaces": self.store.catalog()})
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks":
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.OK, {"tasks": self.store.tasks(workspace_id)})
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "runs":
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.OK, {"runs": self.store.runs(workspace_id)})
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "claims":
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.OK, {"claims": self.store.claims(workspace_id)})
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "sources":
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.OK, {"sources": self.store.sources(workspace_id)})
            if len(parts) == 6 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks" and parts[5] == "missions":
                workspace_id = self._workspace_id(parts, 2)
                task_id = self._task_id(parts, 4)
                return self._send(HTTPStatus.OK, {"missions": self.store.missions(workspace_id, task_id)})
            if len(parts) == 7 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks" and parts[5] == "missions":
                workspace_id = self._workspace_id(parts, 2)
                task_id = self._task_id(parts, 4)
                return self._send(HTTPStatus.OK, self.store.mission(workspace_id, task_id, self._mission_id(parts, 6)))
            if len(parts) == 3 and parts[:2] == ["api", "workspaces"]:
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.OK, self.store.workspace(workspace_id))
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        self._handle(action)

    def do_PATCH(self) -> None:  # noqa: N802
        parts = [part for part in self.path.split("?")[0].split("/") if part]

        def action() -> None:
            payload = self._json()
            if len(parts) == 3 and parts[:2] == ["api", "workspaces"]:
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.OK, self.store.update_workspace(workspace_id, payload))
            if len(parts) == 5 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks":
                workspace_id = self._workspace_id(parts, 2)
                task_id = self._task_id(parts, 4)
                return self._send(HTTPStatus.OK, self.store.update_task(workspace_id, task_id, payload))
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        self._handle(action)

    def do_POST(self) -> None:  # noqa: N802
        parts = [part for part in self.path.split("?")[0].split("/") if part]

        def action() -> None:
            payload = self._json()
            if parts == ["api", "governance", "commands"]:
                from holodeck_control_plane.governance_commands import (
                    submit_governance_command_request,
                )

                result = submit_governance_command_request(self.store.database, payload)
                status = (
                    HTTPStatus.CREATED
                    if result["receipt"]["outcome"] == "accepted"
                    else HTTPStatus.OK
                )
                return self._send(status, result)
            if parts == ["api", "workspaces"]:
                return self._send(HTTPStatus.CREATED, self.store.create_workspace(payload))
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "sources":
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.CREATED, self.store.create_source(workspace_id, payload))
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks":
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.CREATED, self.store.create_task(workspace_id, payload))
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "runs":
                workspace_id = self._workspace_id(parts, 2)
                return self._send(HTTPStatus.CREATED, self.store.begin_run(workspace_id, payload))
            if len(parts) == 6 and parts[:2] == ["api", "workspaces"] and parts[3] == "runs" and parts[5] == "complete":
                workspace_id = self._workspace_id(parts, 2)
                run_id = self._run_id(parts, 4)
                return self._send(HTTPStatus.OK, self.store.complete_run(workspace_id, run_id, payload))
            if len(parts) == 6 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks" and parts[5] == "curator-proposals":
                workspace_id = self._workspace_id(parts, 2)
                task_id = self._task_id(parts, 4)
                return self._send(HTTPStatus.CREATED, self.store.propose(workspace_id, task_id, payload))
            if len(parts) == 8 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks" and parts[5] == "curator-proposals" and parts[7] == "approve":
                workspace_id = self._workspace_id(parts, 2)
                task_id = self._task_id(parts, 4)
                return self._send(HTTPStatus.OK, self.store.approve_proposal(workspace_id, task_id, self._proposal_id(parts, 6)))
            if len(parts) == 6 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks" and parts[5] == "missions":
                workspace_id = self._workspace_id(parts, 2)
                task_id = self._task_id(parts, 4)
                return self._send(HTTPStatus.CREATED, self.store.compile_mission(workspace_id, task_id, payload))
            if len(parts) == 8 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks" and parts[5] == "missions" and parts[7] == "evidence":
                workspace_id = self._workspace_id(parts, 2)
                task_id = self._task_id(parts, 4)
                return self._send(HTTPStatus.CREATED, self.store.add_evidence(workspace_id, task_id, self._mission_id(parts, 6), payload))
            if len(parts) == 8 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks" and parts[5] == "missions" and parts[7] == "accept":
                workspace_id = self._workspace_id(parts, 2)
                task_id = self._task_id(parts, 4)
                return self._send(HTTPStatus.OK, self.store.accept_mission(workspace_id, task_id, self._mission_id(parts, 6)))
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        self._handle(action)


def serve(
    *,
    database: str,
    host: str = "127.0.0.1",
    port: int = 8787,
    insecure_bind: bool = False,
    request_timeout_seconds: int | None = None,
    max_concurrent_requests: int | None = None,
) -> None:
    bind_host = validate_bind_host(host, insecure_bind=insecure_bind)
    handler = type(
        "HolodeckHandler",
        (Handler,),
        {"store": Store(database), "runtime_host": bind_host, "runtime_port": port},
    )
    kwargs: dict[str, int] = {}
    if request_timeout_seconds is not None:
        kwargs["request_timeout_seconds"] = request_timeout_seconds
    if max_concurrent_requests is not None:
        kwargs["max_concurrent_requests"] = max_concurrent_requests
    server = create_http_server((bind_host, port), handler, **kwargs)
    server.serve_forever()
