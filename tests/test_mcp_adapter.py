from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from http import HTTPStatus

import pytest

from holodeck.api import API_VERSION
from holodeck.http_client import HolodeckClientError, HolodeckHttpClient
from holodeck.http_server import create_http_server
from holodeck.service import Handler
from holodeck.store import Store

pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _start_http_server(store: Store):
    handler = type("TestHandler", (Handler,), {"store": store, "runtime_host": "127.0.0.1", "runtime_port": 0})
    server = create_http_server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    return server, thread, base


def _mcp_server_params(base_url: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "holodeck.mcp_server", "--base-url", base_url],
        env={**os.environ, "PYTHONPATH": os.pathsep.join([os.path.join(os.getcwd(), "src"), os.environ.get("PYTHONPATH", "")])},
    )


def _tool_text(result) -> dict:
    assert not result.isError, result.content
    assert result.content
    return json.loads(result.content[0].text)


async def _call_tool(base_url: str, name: str, arguments: dict):
    async with stdio_client(_mcp_server_params(base_url)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(name, arguments)


def test_http_client_surfaces_api_errors(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_http_server(store)
    client = HolodeckHttpClient(base)
    try:
        with pytest.raises(HolodeckClientError) as error:
            client.list_tasks("missing")
        assert error.value.status == HTTPStatus.NOT_FOUND
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mcp_lists_runtime_and_coordinates_run(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_http_server(store)
    try:

        async def flow():
            async with stdio_client(_mcp_server_params(base)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    assert "holodeck_begin_run" in names
                    assert "holodeck_complete_run" in names

                    runtime = _tool_text(await session.call_tool("holodeck_get_runtime", {}))
                    assert runtime["api"]["version"] == API_VERSION

                    workspace = _tool_text(
                        await session.call_tool(
                            "holodeck_create_workspace",
                            {"workspace_id": "demo", "artifact_roots": ["."]},
                        )
                    )
                    assert workspace["workspace_id"] == "demo"

                    task = _tool_text(
                        await session.call_tool(
                            "holodeck_create_task",
                            {"workspace_id": "demo", "title": "MCP task", "status": "ready"},
                        )
                    )

                    run = _tool_text(
                        await session.call_tool(
                            "holodeck_begin_run",
                            {
                                "workspace_id": "demo",
                                "task_id": task["task_id"],
                                "claimed_paths": ["src"],
                                "agent_id": "mcp-test",
                            },
                        )
                    )
                    assert run["status"] == "active"

                    claims = _tool_text(await session.call_tool("holodeck_list_claims", {"workspace_id": "demo"}))
                    assert claims["claims"][0]["status"] == "active"

                    completed = _tool_text(
                        await session.call_tool(
                            "holodeck_complete_run",
                            {"workspace_id": "demo", "run_id": run["run_id"], "summary": "done"},
                        )
                    )
                    assert completed["status"] == "completed"

                    claims = _tool_text(await session.call_tool("holodeck_list_claims", {"workspace_id": "demo"}))
                    assert claims["claims"][0]["status"] == "released"

        asyncio.run(flow())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mcp_reports_conflict_for_overlapping_claim(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_http_server(store)
    store.create_workspace({"workspace_id": "demo"})
    task = store.create_task("demo", {"title": "Race", "status": "ready"})
    store.begin_run("demo", {"task_id": task["task_id"], "claimed_paths": ["src"]})
    try:

        async def attempt():
            async with stdio_client(_mcp_server_params(base)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(
                        "holodeck_begin_run",
                        {
                            "workspace_id": "demo",
                            "task_id": task["task_id"],
                            "claimed_paths": ["src/api.py"],
                        },
                    )

        result = asyncio.run(attempt())
        assert result.isError
        assert "409" in result.content[0].text or "overlaps active work" in result.content[0].text
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_independent_mcp_sessions_cannot_claim_same_path(tmp_path):
    store = Store(tmp_path / "runtime.db")
    server, thread, base = _start_http_server(store)
    store.create_workspace({"workspace_id": "demo"})
    task = store.create_task("demo", {"title": "Race", "status": "ready"})
    try:

        async def begin():
            return await _call_tool(
                base,
                "holodeck_begin_run",
                {"workspace_id": "demo", "task_id": task["task_id"], "claimed_paths": ["src"]},
            )

        async def race():
            return await asyncio.gather(begin(), begin())

        first, second = asyncio.run(race())
        outcomes = []
        for result in (first, second):
            if isinstance(result, Exception):
                outcomes.append("error")
            elif result.isError:
                outcomes.append("error")
            else:
                outcomes.append("ok")
        assert outcomes.count("ok") == 1
        assert outcomes.count("error") == 1
        active = [claim for claim in store.claims("demo") if claim["status"] == "active"]
        assert len(active) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
