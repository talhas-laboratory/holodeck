# Holodeck HTTP API v1 (alpha)

Local coordination API served by `holodeck serve`. All paths are relative to the runtime base URL (default `http://127.0.0.1:8787`).

## Versioning

Clients must read `GET /api/config` and inspect the `api` object before integrating:

| Field | Value (current) | Meaning |
|---|---|---|
| `version` | `"1"` | Contract major version |
| `stability` | `"alpha"` | Breaking changes are allowed only with a version bump |
| `contract` | `"http-api-v1"` | Stable name for this document |
| `max_json_body_bytes` | `65536` | Maximum mutation body size |

**Breaking-change policy:** incompatible changes to paths, required fields, status codes, or error semantics require incrementing `api.version`. Additive JSON fields may appear without a version bump while `stability` is `alpha`.

## Transport

- JSON request bodies require `Content-Type: application/json` and an explicit `Content-Length`.
- JSON responses use `Content-Type: application/json`.
- Mutation bodies must be JSON objects (not arrays or scalars).

## Errors

Failed API requests return a JSON object:

```json
{"error": "human-readable message"}
```

| HTTP status | When |
|---|---|
| `400` | Malformed JSON, missing/invalid `Content-Length`, non-object body |
| `404` | Workspace, task, or run not found |
| `409` | Duplicate workspace/task or overlapping active claim |
| `413` | Body larger than `max_json_body_bytes` |
| `415` | `Content-Type` is not `application/json` |
| `422` | Validation failure (identifiers, lifecycle, path grammar) |
| `503` | SQLite contention (`database is busy`) |

## Endpoints

### `GET /health`

Liveness probe.

**Response `200`**

```json
{"status": "ok"}
```

### `GET /api/config`

Runtime metadata, advisory policy, capabilities, and API contract identity.

**Response `200`**

```json
{
  "api": {
    "version": "1",
    "stability": "alpha",
    "contract": "http-api-v1",
    "documentation": "docs/http-api-v1.md",
    "max_json_body_bytes": 65536,
    "breaking_change_policy": "..."
  },
  "runtime": {
    "host": "127.0.0.1",
    "port": 8787,
    "database": "/path/to/holodeck.db",
    "storage": "sqlite",
    "authority": "local"
  },
  "project_manifest": { "schema_version": "1.0", "...": "..." },
  "onboarding_policy": { "schema_version": "1.0", "actions": { } },
  "policy_enforcement": "advisory",
  "capabilities": [ { "id": "workspaces", "status": "available" } ]
}
```

`policy_enforcement` is always `advisory` in v1: Holodeck does not intercept or block project actions.

### `GET /api/workspaces`

List workspaces (newest first).

**Response `200`**

```json
{"workspaces": [ { "workspace_id": "demo", "label": "...", "artifact_roots": ["."], "scope_out": [], "status": "active" } ]}
```

### `POST /api/workspaces`

Create a workspace.

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `workspace_id` | string | yes | URL-safe identifier |
| `label` | string | no | Defaults to `workspace_id` |
| `goal` | string | no | |
| `purpose` | string | no | |
| `artifact_roots` | string[] | no | Defaults to `["."]`; must be a JSON array of strings |
| `scope_out` | string[] | no | Repository-relative paths excluded from claims |

**Response `201`** — workspace record.

**Errors:** `409` duplicate `workspace_id`; `422` invalid identifier or list fields.

### `GET /api/workspaces/{workspace_id}`

Fetch one workspace.

**Response `200`** — workspace record. **`404`** if missing. **`422`** if `workspace_id` is not a valid identifier.

### `PATCH /api/workspaces/{workspace_id}`

Update workspace fields. Accepted keys: `label`, `goal`, `purpose`, `artifact_roots`, `scope_out`.

**Response `200`** — updated workspace. **`404`** if missing.

### `GET /api/workspaces/{workspace_id}/tasks`

**Response `200`**

```json
{"tasks": [ { "task_id": "task-abc", "title": "...", "status": "ready", "acceptance_criteria": [], "constraints": [] } ]}
```

Task `status` is one of: `backlog`, `ready`, `in-progress`, `review`, `blocked`, `done`, `cancelled`.

### `POST /api/workspaces/{workspace_id}/tasks`

**Body**

| Field | Type | Required |
|---|---|---|
| `title` | string | yes |
| `task_id` | string | no | Generated if omitted |
| `status` | string | no | Defaults to `backlog` |
| `acceptance_criteria` | string[] | no |
| `constraints` | string[] | no |

**Response `201`** — task record. **`409`** duplicate `task_id` in workspace.

### `PATCH /api/workspaces/{workspace_id}/tasks/{task_id}`

Update `title`, `status`, `acceptance_criteria`, or `constraints`.

**Response `200`** — updated task. **`422`** illegal status transition. **`409`** concurrent status update lost compare-and-swap.

### `GET /api/workspaces/{workspace_id}/runs`

**Response `200`**

```json
{"runs": [ { "run_id": "run-abc", "task_id": "task-abc", "status": "active", "claimed_paths": ["src"], "agent_id": "codex" } ]}
```

Run `status`: `active`, `completed`, `failed`, `cancelled`.

### `POST /api/workspaces/{workspace_id}/runs`

Begin a run and acquire path claims.

**Body**

| Field | Type | Required |
|---|---|---|
| `task_id` | string | yes |
| `claimed_paths` | string[] | yes | Repository-relative POSIX paths |
| `agent_id` | string | no | Defaults to `"unknown"` |
| `intent` | string | no | |

**Response `201`** — run record with normalized `claimed_paths`.

**Errors:** `409` overlapping active claim or duplicate paths in request; `422` task not found, terminal task status, or invalid path.

### `POST /api/workspaces/{workspace_id}/runs/{run_id}/complete`

Complete an active run and release its claims.

**Body**

| Field | Type | Required |
|---|---|---|
| `status` | string | no | Terminal status; defaults to `completed` |
| `summary` | string | no | |

**Response `200`** — updated run. **`422`** if run is not `active`. **`404`** if run missing.

### `GET /api/workspaces/{workspace_id}/claims`

**Response `200`**

```json
{"claims": [ { "claim_id": "claim-abc", "run_id": "run-abc", "path": "src", "status": "active" } ]}
```

Claim `status`: `active`, `released`.

## Identifiers

Path parameters `workspace_id`, `task_id`, and `run_id` must match:

```text
^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$
```

## Path claims

Claim paths are repository-relative, use forward slashes, reject `..`, and are normalized to Unicode NFC. A claim must fall under a workspace `artifact_root` and must not intersect `scope_out`.
