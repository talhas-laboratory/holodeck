from pathlib import Path


def test_dockerignore_excludes_local_artifacts():
    contents = Path(".dockerignore").read_text(encoding="utf-8")
    for pattern in (".git", ".holodeck", ".venv", ".pytest_cache", "*.db", "tests/"):
        assert pattern in contents


def test_dockerfile_runs_as_non_root():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "USER holodeck" in dockerfile
    assert "COPY pyproject.toml README.md LICENSE-MIT LICENSE-APACHE ./" in dockerfile
    assert "COPY src ./src" in dockerfile
    assert "COPY . ." not in dockerfile
    assert "python:3.13.7-slim-bookworm@sha256:" in dockerfile


def test_compose_drops_linux_capabilities():
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    assert "cap_drop:" in compose
    assert "- ALL" in compose


def test_release_verifier_uses_an_isolated_virtual_environment():
    script = Path("scripts/verify_release.sh").read_text(encoding="utf-8")
    assert "mktemp -d" in script
    assert '"$TEST_PYTHON" -m pip install -e ".[dev]"' in script
    assert '"$TEST_PYTHON" -m build --outdir "$DIST_DIR" "$VERIFY_SOURCE"' in script
    assert '"$INSTALL_PYTHON" -m pip install "$WHEEL"' in script
    assert '"$ROOT/LICENSE-MIT" "$ROOT/LICENSE-APACHE" "$VERIFY_SOURCE/"' in script
    assert 'from importlib.resources import files' in script
    assert 'distribution("holodeck-control-plane")' in script
    assert '"$INSTALL_ENV/bin/holodeck" serve' in script
    assert 'docker volume rm "$VOLUME"' in script


def test_package_metadata_declares_a_published_readme_and_project_links():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'readme = "README.md"' in pyproject
    assert 'license = "MIT OR Apache-2.0"' in pyproject
    assert 'Homepage = "https://github.com/talhas-laboratory/holodeck"' in pyproject
    assert 'Source = "https://github.com/talhas-laboratory/holodeck"' in pyproject
    assert Path("LICENSE-MIT").is_file()
    assert Path("LICENSE-APACHE").is_file()
