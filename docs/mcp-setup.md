# Holodeck MCP setup

The Holodeck MCP adapter is a thin client over the local HTTP API (`http-api-v1`). It does not enforce project policy; it only coordinates workspaces, tasks, runs, and path claims.

## Prerequisites

1. Install Holodeck with the MCP extra:

```bash
python -m pip install 'holodeck-control-plane[mcp]'
```

2. Start the local runtime in another terminal:

```bash
holodeck serve --database .holodeck/runtime.db
```

3. Confirm the API is up:

```bash
curl http://127.0.0.1:8787/health
curl http://127.0.0.1:8787/api/config
```

## Cursor / Claude Desktop configuration

Add an MCP server entry that launches the adapter against your local runtime:

```json
{
  "mcpServers": {
    "holodeck": {
      "command": "holodeck",
      "args": ["mcp", "--base-url", "http://127.0.0.1:8787"]
    }
  }
}
```

If `holodeck` is not on your `PATH`, use the full path to the executable from your virtual environment.

## Tools exposed

| Tool | Purpose |
|---|---|
| `holodeck_get_runtime` | Read API version and runtime metadata |
| `holodeck_list_workspaces` | List workspaces |
| `holodeck_create_workspace` | Create a workspace |
| `holodeck_list_tasks` | List tasks in a workspace |
| `holodeck_create_task` | Create a task |
| `holodeck_list_runs` | List runs |
| `holodeck_list_claims` | List active and released claims |
| `holodeck_begin_run` | Claim paths and start a run |
| `holodeck_complete_run` | Complete a run and release its claims |

## Typical agent flow

1. `holodeck_get_runtime` — confirm `api.version` is `1`.
2. `holodeck_list_workspaces` / `holodeck_create_workspace` — pick or create a workspace.
3. `holodeck_list_tasks` / `holodeck_create_task` — pick or create a ready task.
4. `holodeck_begin_run` — claim repository-relative paths before editing files.
5. Do work locally.
6. `holodeck_complete_run` — release claims when finished.

## Errors

Tool failures surface as MCP tool errors with messages such as `holodeck api error (409): claimed path overlaps active work`. The numeric code matches the HTTP status from the Holodeck API.

## Notes

- Run one Holodeck HTTP runtime per machine/database; run one MCP adapter process per agent client session.
- Overlapping active path claims are rejected even across independent MCP sessions because the HTTP runtime is the single authority.
