# Holodeck Runtime

Holodeck Runtime is a local-first, self-hosted control plane for bounded autonomous development. It keeps workspace intent, task scope, agent runs, and file-path claims in one portable SQLite-backed service.

It is deliberately independent of OpenClaw, Telegram, and any hosted control plane. The included Compose file is a reference deployment only.

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

Open `http://127.0.0.1:8787/` for the standalone Holodeck dashboard. The frontend is packaged and served by this runtime; it has no Conversation OS or Inner World dependency.

## Minimal API

- `GET /health`
- `GET /api/config`
- `GET|POST /api/workspaces`
- `GET|PATCH /api/workspaces/<workspace_id>`
- `GET|POST /api/workspaces/<workspace_id>/tasks`
- `PATCH /api/workspaces/<workspace_id>/tasks/<task_id>`
- `GET /api/workspaces/<workspace_id>/runs`
- `POST /api/workspaces/<workspace_id>/runs`
- `POST /api/workspaces/<workspace_id>/runs/<run_id>/complete`
- `GET /api/workspaces/<workspace_id>/claims`

The dashboard reflects the complete alpha surface: workspace boundaries, full task records, agent runs, active and released path claims, runtime settings, project manifest defaults, onboarding policy, and the implemented/planned capability boundary. The alpha refuses overlapping active file claims inside a workspace and releases them when a run completes. Future releases add verification evidence, handoffs, repository discovery, and agent/CI adapters.

## Safe onboarding

Run `holodeck init` inside a Git repository. It creates only `.holodeck/manifest.json` and `.holodeck/policy.json`; it does not edit source, install dependencies, create a Git remote, or start a service.

The default policy allows repository reads and workspace-state changes automatically. Source edits, dependencies, network access, Git pushes, and deployments require approval; destructive commands are denied. Inspect a decision with `holodeck policy-check deploy`.

## Development and release verification

```bash
pip install -e ".[dev]"
python -m pytest -q
./scripts/verify_release.sh
```

`verify_release.sh` runs the test suite, smoke-tests a clean package install, and builds the container image for a `/health` check when Docker is available.

### Git remotes

`origin` is configured with two `pushurl` entries (`holodeck` and `holodeck-runtime`). A plain `git push origin` updates both repositories. Push to one repo only with `git push origin main` using a single push URL, or add named remotes such as `runtime` and run `git push runtime main`.
