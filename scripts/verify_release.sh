#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Installing package with dev dependencies"
python3 -m pip install -e ".[dev]"

echo "==> Running tests"
python3 -m pytest -q

echo "==> Smoke testing clean install"
python3 -m pip install .
holodeck --help >/dev/null

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Docker not available; skipping container smoke test"
  exit 0
fi

IMAGE="holodeck-runtime:verify"
CONTAINER="holodeck-verify-$$"
PORT="${HOLODECK_VERIFY_PORT:-9876}"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Building container image"
docker build -t "$IMAGE" .

echo "==> Starting container smoke test on port ${PORT}"
docker run -d --name "$CONTAINER" -p "127.0.0.1:${PORT}:8787" -v "${CONTAINER}-data:/data" "$IMAGE" >/dev/null

for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
    echo "==> Container health check passed"
    exit 0
  fi
  sleep 1
done

echo "Container health check failed" >&2
exit 1
