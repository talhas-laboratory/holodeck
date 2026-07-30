# Holodeck

Holodeck is a local-first, self-hosted control plane for bounded autonomous development. It keeps workspace intent, task scope, agent runs, and file-path claims in one portable SQLite-backed service.

It is deliberately independent of OpenClaw, Telegram, and any hosted control plane. The included Compose file is a reference deployment only.

## Product direction

The durable product vision and decision rules live in
[docs/product-vision/](docs/product-vision/README.md). They describe Holodeck as
the governed execution kernel behind collaboration surfaces such as Block's
Buzz: humans initiate work in the platform they already use, while Holodeck
compiles intent into bounded missions, provisions execution workspaces,
coordinates agents, and controls evidence-based acceptance.

Implementation specifications and historical work remain under
[docs/work-to-be-done/](docs/work-to-be-done/README.md); they do not replace the
product vision.

## Install and run locally

Install the published package (once a release is available) into a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install holodeck-control-plane
holodeck init
holodeck serve --database .holodeck/runtime.db
```

For development from a checkout, use an editable install instead:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
holodeck init
holodeck serve --database .holodeck/runtime.db
```

Or run the self-contained reference deployment:

```bash
docker compose up --build -d
curl http://127.0.0.1:8787/health
```

Open `http://127.0.0.1:8787/` for the standalone Holodeck dashboard. The frontend is packaged and served by this runtime; it has no Conversation OS or Inner World dependency.

### Local daemon limits

Holodeck deliberately uses Python's standard-library threaded HTTP server for the local, loopback-only alpha. It permits up to 64 active request handlers, keeps an eight-connection listen backlog, and applies a 30-second socket timeout; requests above the active-handler limit receive `503`. It shuts down cleanly through the server control path. It does not provide TLS, HTTP/2, authentication, rate limiting, or a remote-production deployment profile. Non-loopback binding requires `--insecure-bind` and remains unsuitable for untrusted networks.

## Minimal API

Stable contract: [docs/http-api-v1.md](docs/http-api-v1.md) (also served at `GET /docs/http-api-v1` from a running runtime). Discover the active version at `GET /api/config` (`api.version`, currently `1`).

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

## MCP agent adapter

Install with the optional MCP extra and point an MCP-capable client at the local runtime:

```bash
python -m pip install 'holodeck-control-plane[mcp]'
holodeck serve --database .holodeck/runtime.db
holodeck mcp --base-url http://127.0.0.1:8787
```

Setup for Cursor, Claude Desktop, and the full tool list: [docs/mcp-setup.md](docs/mcp-setup.md). The adapter is a thin HTTP client over the documented API; it does not enforce project policy.

## Safe onboarding

Run `holodeck init` inside a Git repository. It creates only `.holodeck/manifest.json` and `.holodeck/policy.json`; it does not edit source, install dependencies, create a Git remote, or start a service.

The default policy labels repository reads and workspace-state changes as automatic; source edits, dependencies, network access, Git pushes, and deployments as approval-required; and destructive commands as denied. These are advisory decisions only: Holodeck does not currently intercept, enforce, or block those actions. Inspect a decision with `holodeck policy-check deploy`.

## Development and release verification

```bash
pip install -e ".[dev]"
python -m pytest -q
./scripts/verify_release.sh
```

`verify_release.sh` runs the test suite, smoke-tests a clean package install, and builds the container image for a `/health` check when Docker is available.

## Project repository

Holodeck's canonical public repository is [talhas-laboratory/holodeck](https://github.com/talhas-laboratory/holodeck). A plain `git push origin` updates only that repository.

## License

Holodeck is dual-licensed under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option.
