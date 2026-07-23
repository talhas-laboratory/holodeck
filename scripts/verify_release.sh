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

frontend = files("holodeck").joinpath("frontend")
for asset in ("index.html", "app.js", "styles.css"):
    assert frontend.joinpath(asset).is_file(), asset
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
kill "$INSTALL_SERVER_PID"
wait "$INSTALL_SERVER_PID" 2>/dev/null || true
INSTALL_SERVER_PID=""

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Docker not available; skipping container smoke test"
  exit 0
fi

IMAGE="holodeck:verify"
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
