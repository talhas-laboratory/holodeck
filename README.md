# Holodeck Runtime

Holodeck Runtime is a local-first, self-hosted control plane for bounded autonomous development. It keeps workspace intent, task scope, agent runs, and file-path claims in one portable SQLite-backed service.

It is deliberately independent of Inner Space, OpenClaw, Telegram, and any hosted control plane. The included Compose file is a reference deployment only.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
holodeck init
holodeck serve --database .holodeck/runtime.db
```

Or run the self-contained reference deployment:

```bash
docker compose up --build -d
curl http://127.0.0.1:8787/health
```

## Minimal API

- `GET /health`
- `GET|POST /api/workspaces`
- `GET /api/workspaces/<workspace_id>`
- `GET|POST /api/workspaces/<workspace_id>/tasks`
- `POST /api/workspaces/<workspace_id>/runs`

The alpha refuses overlapping active file claims inside a workspace. Future releases add verification evidence, handoffs, policy classes, repository discovery, and agent/CI adapters.

## Safe onboarding

Run `holodeck init` inside a Git repository. It creates only `.holodeck/manifest.json` and `.holodeck/policy.json`; it does not edit source, install dependencies, create a Git remote, or start a service.

The default policy allows repository reads and workspace-state changes automatically. Source edits, dependencies, network access, Git pushes, and deployments require approval; destructive commands are denied. Inspect a decision with `holodeck policy-check deploy`.
