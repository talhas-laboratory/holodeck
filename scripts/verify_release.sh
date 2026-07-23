#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BOOTSTRAP_PYTHON="${PYTHON:-python3}"
VERIFY_ROOT="$(mktemp -d)"
TEST_ENV="$VERIFY_ROOT/test-env"
TEST_PYTHON="$TEST_ENV/bin/python"
INSTALL_ENV="$VERIFY_ROOT/install-env"
INSTALL_PYTHON="$INSTALL_ENV/bin/python"
VERIFY_SOURCE="$VERIFY_ROOT/source"
DIST_DIR="$VERIFY_ROOT/dist"
WHEEL=""
INSTALL_SERVER_PID=""
CONTAINER=""
VOLUME=""
IMAGE=""

cleanup() {
  if [[ -n "$INSTALL_SERVER_PID" ]]; then
    kill "$INSTALL_SERVER_PID" >/dev/null 2>&1 || true
    wait "$INSTALL_SERVER_PID" 2>/dev/null || true
  fi
  if [[ -n "$CONTAINER" ]]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  fi
  if [[ -n "$VOLUME" ]]; then
    docker volume rm "$VOLUME" >/dev/null 2>&1 || true
  fi
  if [[ -n "$IMAGE" ]]; then
    docker rmi "$IMAGE" >/dev/null 2>&1 || true
  fi
  rm -rf "$VERIFY_ROOT"
}
trap cleanup EXIT

echo "==> Creating isolated test environment"
"$BOOTSTRAP_PYTHON" -m venv "$TEST_ENV"

echo "==> Installing package with dev dependencies"
"$TEST_PYTHON" -m pip install -e ".[dev]"

echo "==> Running tests"
"$TEST_PYTHON" -m pytest -q

echo "==> Building source and wheel distributions"
mkdir -p "$VERIFY_SOURCE"
cp "$ROOT/pyproject.toml" "$ROOT/README.md" "$VERIFY_SOURCE/"
cp "$ROOT/LICENSE-MIT" "$ROOT/LICENSE-APACHE" "$VERIFY_SOURCE/"
cp -R "$ROOT/src" "$VERIFY_SOURCE/src"
"$TEST_PYTHON" -m build --outdir "$DIST_DIR" "$VERIFY_SOURCE"
WHEEL="$(find "$DIST_DIR" -maxdepth 1 -name '*.whl' -print -quit)"
if [[ -z "$WHEEL" ]]; then
  echo "Wheel build failed" >&2
  exit 1
fi

echo "==> Smoke testing a clean wheel install"
"$BOOTSTRAP_PYTHON" -m venv "$INSTALL_ENV"
"$INSTALL_PYTHON" -m pip install "$WHEEL"
"$INSTALL_ENV/bin/holodeck" --help >/dev/null
"$INSTALL_PYTHON" -c '
from importlib.metadata import distribution
from importlib.resources import files

frontend = files("holodeck_control_plane").joinpath("frontend")
for asset in ("index.html", "app.js", "styles.css"):
    assert frontend.joinpath(asset).is_file(), asset
docs = files("holodeck_control_plane").joinpath("docs")
for doc in ("http-api-v1.md", "mcp-setup.md"):
    assert docs.joinpath(doc).is_file(), doc
package = distribution("holodeck-control-plane")
for license_file in ("licenses/LICENSE-MIT", "licenses/LICENSE-APACHE"):
    assert package.read_text(license_file), license_file
'

INSTALL_PORT="${HOLODECK_INSTALL_VERIFY_PORT:-9875}"
"$INSTALL_ENV/bin/holodeck" serve --database "$VERIFY_ROOT/runtime.db" --port "$INSTALL_PORT" >"$VERIFY_ROOT/install-server.log" 2>&1 &
INSTALL_SERVER_PID="$!"
for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${INSTALL_PORT}/health" >/dev/null; then
    break
  fi
  sleep 1
done
if ! curl -fsS "http://127.0.0.1:${INSTALL_PORT}/health" >/dev/null; then
  echo "Clean wheel install health check failed" >&2
  exit 1
fi
if ! curl -fsS "http://127.0.0.1:${INSTALL_PORT}/docs/http-api-v1" | grep -q "Holodeck HTTP API v1"; then
  echo "Packaged API documentation is not served from the wheel install" >&2
  exit 1
fi
kill "$INSTALL_SERVER_PID"
wait "$INSTALL_SERVER_PID" 2>/dev/null || true
INSTALL_SERVER_PID=""

echo "==> Smoke testing clean wheel install with MCP extra"
MCP_ENV="$VERIFY_ROOT/mcp-env"
export VERIFY_ROOT MCP_ENV
"$BOOTSTRAP_PYTHON" -m venv "$MCP_ENV"
"$MCP_ENV/bin/python" -m pip install "$WHEEL[mcp]"
VERIFY_ROOT="$VERIFY_ROOT" MCP_ENV="$MCP_ENV" "$MCP_ENV/bin/python" -c '
import asyncio
import json
import os
import sys
import threading
from pathlib import Path

from holodeck_control_plane.http_server import create_http_server
from holodeck_control_plane.service import Handler
from holodeck_control_plane.store import Store
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

db = Path(os.environ["VERIFY_ROOT"]) / "mcp-runtime.db"
store = Store(db)
handler = type("VerifyHandler", (Handler,), {"store": store, "runtime_host": "127.0.0.1", "runtime_port": 0})
server = create_http_server(("127.0.0.1", 0), handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_port}"

async def handshake() -> None:
    params = StdioServerParameters(
        command=os.environ["MCP_ENV"] + "/bin/holodeck",
        args=["mcp", "--base-url", base],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("holodeck_get_runtime", {})
            assert not result.isError, result.content
            payload = json.loads(result.content[0].text)
            assert payload["api"]["version"] == "1"

asyncio.run(handshake())
server.shutdown()
server.server_close()
thread.join(timeout=2)
'

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Docker not available; skipping container smoke test"
  exit 0
fi

IMAGE="holodeck:verify-$$"
CONTAINER="holodeck-verify-$$"
VOLUME="${CONTAINER}-data"
PORT="${HOLODECK_VERIFY_PORT:-9876}"

echo "==> Building container image"
docker build -t "$IMAGE" .

echo "==> Starting container smoke test on port ${PORT}"
docker run -d --name "$CONTAINER" -p "127.0.0.1:${PORT}:8787" -v "${VOLUME}:/data" "$IMAGE" >/dev/null

for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
    echo "==> Container health check passed"
    exit 0
  fi
  sleep 1
done

echo "Container health check failed" >&2
exit 1
