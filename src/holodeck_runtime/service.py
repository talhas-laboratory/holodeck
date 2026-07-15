from __future__ import annotations

import json
import mimetypes
from importlib.resources import files
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .store import Store


class Handler(BaseHTTPRequestHandler):
    store: Store

    def log_message(self, *_: object) -> None:
        return

    def _send(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return dict(json.loads(self.rfile.read(length) or b"{}"))

    def _asset(self, name: str) -> None:
        root = files("holodeck_runtime").joinpath("frontend")
        asset = root.joinpath(name)
        if not asset.is_file():
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
        body = asset.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parts = [part for part in self.path.split("?")[0].split("/") if part]
        try:
            if not parts:
                return self._asset("index.html")
            if len(parts) == 2 and parts[0] == "assets":
                return self._asset(parts[1])
            if parts == ["health"]:
                return self._send(HTTPStatus.OK, {"status": "ok"})
            if parts == ["api", "workspaces"]:
                return self._send(HTTPStatus.OK, {"workspaces": self.store.catalog()})
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks":
                return self._send(HTTPStatus.OK, {"tasks": self.store.tasks(parts[2])})
            if len(parts) == 3 and parts[:2] == ["api", "workspaces"]:
                return self._send(HTTPStatus.OK, self.store.workspace(parts[2]))
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except (KeyError, ValueError) as error:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_POST(self) -> None:  # noqa: N802
        parts = [part for part in self.path.split("?")[0].split("/") if part]
        try:
            payload = self._json()
            if parts == ["api", "workspaces"]:
                return self._send(HTTPStatus.CREATED, self.store.create_workspace(payload))
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "tasks":
                return self._send(HTTPStatus.CREATED, self.store.create_task(parts[2], payload))
            if len(parts) == 4 and parts[:2] == ["api", "workspaces"] and parts[3] == "runs":
                return self._send(HTTPStatus.CREATED, self.store.begin_run(parts[2], payload))
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(error)})


def serve(*, database: str, host: str = "127.0.0.1", port: int = 8787) -> None:
    handler = type("HolodeckHandler", (Handler,), {"store": Store(database)})
    ThreadingHTTPServer((host, port), handler).serve_forever()
