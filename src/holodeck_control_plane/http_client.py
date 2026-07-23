from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from holodeck_control_plane.api import SUPPORTED_API_VERSIONS


class HolodeckClientError(Exception):
    """HTTP API error from a Holodeck runtime."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"HTTP {status}: {message}")


class HolodeckHttpClient:
    """Thin HTTP client for the Holodeck http-api-v1 contract."""

    def __init__(self, base_url: str = "http://127.0.0.1:8787", *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._api_version_verified = False

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(data))
        request = Request(f"{self.base_url}{path}", data=data, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                if not body:
                    return {}
                return json.loads(body)
        except HTTPError as error:
            message = self._error_message(error)
            raise HolodeckClientError(error.code, message) from error

    @staticmethod
    def _error_message(error: HTTPError) -> str:
        try:
            payload = json.loads(error.read())
        except json.JSONDecodeError:
            return error.reason or "request failed"
        if isinstance(payload, dict) and "error" in payload:
            return str(payload["error"])
        return error.reason or "request failed"

    def ensure_api_compatible(self) -> None:
        """Verify the runtime exposes a supported api.version before mutating state."""
        if self._api_version_verified:
            return
        payload = self.get_runtime()
        version = str(payload.get("api", {}).get("version", ""))
        if version not in SUPPORTED_API_VERSIONS:
            supported = ", ".join(sorted(SUPPORTED_API_VERSIONS))
            raise HolodeckClientError(
                0,
                f"unsupported api.version {version!r}; this client supports {supported}",
            )
        self._api_version_verified = True

    def _require_supported_api(self) -> None:
        self.ensure_api_compatible()

    def get_runtime(self) -> dict[str, Any]:
        return self._request("GET", "/api/config")

    def list_workspaces(self) -> list[dict[str, Any]]:
        self._require_supported_api()
        payload = self._request("GET", "/api/workspaces")
        return list(payload.get("workspaces", []))

    def create_workspace(self, manifest: dict[str, Any]) -> dict[str, Any]:
        self._require_supported_api()
        return self._request("POST", "/api/workspaces", manifest)

    def list_tasks(self, workspace_id: str) -> list[dict[str, Any]]:
        self._require_supported_api()
        payload = self._request("GET", f"/api/workspaces/{workspace_id}/tasks")
        return list(payload.get("tasks", []))

    def create_task(self, workspace_id: str, task: dict[str, Any]) -> dict[str, Any]:
        self._require_supported_api()
        return self._request("POST", f"/api/workspaces/{workspace_id}/tasks", task)

    def list_runs(self, workspace_id: str) -> list[dict[str, Any]]:
        self._require_supported_api()
        payload = self._request("GET", f"/api/workspaces/{workspace_id}/runs")
        return list(payload.get("runs", []))

    def list_claims(self, workspace_id: str) -> list[dict[str, Any]]:
        self._require_supported_api()
        payload = self._request("GET", f"/api/workspaces/{workspace_id}/claims")
        return list(payload.get("claims", []))

    def begin_run(self, workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._require_supported_api()
        return self._request("POST", f"/api/workspaces/{workspace_id}/runs", body)

    def complete_run(self, workspace_id: str, run_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        self._require_supported_api()
        return self._request("POST", f"/api/workspaces/{workspace_id}/runs/{run_id}/complete", body or {})
