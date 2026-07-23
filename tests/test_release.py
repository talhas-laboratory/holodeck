from pathlib import Path


def test_dockerignore_excludes_local_artifacts():
    contents = Path(".dockerignore").read_text(encoding="utf-8")
    for pattern in (".git", ".holodeck", ".venv", ".pytest_cache", "*.db", "tests/"):
        assert pattern in contents


def test_dockerfile_runs_as_non_root():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "USER holodeck" in dockerfile
    assert "COPY src ./src" in dockerfile
    assert "COPY . ." not in dockerfile
    assert "python:3.13.7-slim-bookworm@sha256:" in dockerfile


def test_compose_drops_linux_capabilities():
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    assert "cap_drop:" in compose
    assert "- ALL" in compose
