from __future__ import annotations

import argparse
from typing import Any

from holodeck_control_plane.http_client import HolodeckClientError, HolodeckHttpClient


def _tool_error(error: HolodeckClientError) -> RuntimeError:
    return RuntimeError(f"holodeck api error ({error.status}): {error.message}")


def create_mcp_server(client: HolodeckHttpClient):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise SystemExit(
            "holodeck mcp requires the optional MCP dependency; install with: pip install 'holodeck-control-plane[mcp]'"
        ) from error

    mcp = FastMCP(
        "holodeck",
        instructions=(
            "Holodeck coordinates local agent work: workspaces, tasks, path claims, and runs. "
            "Call holodeck_get_runtime first to read the API contract version. Policy is advisory only."
        ),
    )

    @mcp.tool()
    def holodeck_get_runtime() -> dict[str, Any]:
        """Return Holodeck runtime metadata, API contract version, and advisory policy settings."""
        try:
            return client.get_runtime()
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    @mcp.tool()
    def holodeck_list_workspaces() -> dict[str, Any]:
        """List all workspaces."""
        try:
            return {"workspaces": client.list_workspaces()}
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    @mcp.tool()
    def holodeck_create_workspace(
        workspace_id: str,
        label: str = "",
        goal: str = "",
        purpose: str = "",
        artifact_roots: list[str] | None = None,
        scope_out: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a workspace with optional boundaries."""
        body: dict[str, Any] = {"workspace_id": workspace_id}
        if label:
            body["label"] = label
        if goal:
            body["goal"] = goal
        if purpose:
            body["purpose"] = purpose
        if artifact_roots is not None:
            body["artifact_roots"] = artifact_roots
        if scope_out is not None:
            body["scope_out"] = scope_out
        try:
            return client.create_workspace(body)
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    @mcp.tool()
    def holodeck_list_tasks(workspace_id: str) -> dict[str, Any]:
        """List tasks in a workspace."""
        try:
            return {"tasks": client.list_tasks(workspace_id)}
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    @mcp.tool()
    def holodeck_create_task(
        workspace_id: str,
        title: str,
        task_id: str = "",
        status: str = "ready",
        acceptance_criteria: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a task in a workspace."""
        body: dict[str, Any] = {"title": title, "status": status}
        if task_id:
            body["task_id"] = task_id
        if acceptance_criteria is not None:
            body["acceptance_criteria"] = acceptance_criteria
        if constraints is not None:
            body["constraints"] = constraints
        try:
            return client.create_task(workspace_id, body)
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    @mcp.tool()
    def holodeck_list_runs(workspace_id: str) -> dict[str, Any]:
        """List runs in a workspace."""
        try:
            return {"runs": client.list_runs(workspace_id)}
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    @mcp.tool()
    def holodeck_list_claims(workspace_id: str) -> dict[str, Any]:
        """List path claims in a workspace."""
        try:
            return {"claims": client.list_claims(workspace_id)}
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    @mcp.tool()
    def holodeck_begin_run(
        workspace_id: str,
        task_id: str,
        claimed_paths: list[str],
        agent_id: str = "mcp",
        intent: str = "",
    ) -> dict[str, Any]:
        """Begin a run and acquire exclusive path claims for a task."""
        body = {
            "task_id": task_id,
            "claimed_paths": claimed_paths,
            "agent_id": agent_id,
            "intent": intent,
        }
        try:
            return client.begin_run(workspace_id, body)
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    @mcp.tool()
    def holodeck_complete_run(
        workspace_id: str,
        run_id: str,
        summary: str = "",
        status: str = "completed",
    ) -> dict[str, Any]:
        """Complete a run and release its active path claims."""
        body: dict[str, Any] = {"status": status}
        if summary:
            body["summary"] = summary
        try:
            return client.complete_run(workspace_id, run_id, body)
        except HolodeckClientError as error:
            raise _tool_error(error) from error

    return mcp


def run_mcp(*, base_url: str) -> None:
    client = HolodeckHttpClient(base_url)
    try:
        client.ensure_api_compatible()
    except HolodeckClientError as error:
        raise SystemExit(f"holodeck mcp: {error.message}") from error
    server = create_mcp_server(client)
    server.run(transport="stdio")


def main() -> None:
    parser = argparse.ArgumentParser(description="Holodeck MCP adapter")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8787",
        help="Base URL of a running Holodeck HTTP runtime",
    )
    args = parser.parse_args()
    run_mcp(base_url=args.base_url)


if __name__ == "__main__":
    main()
