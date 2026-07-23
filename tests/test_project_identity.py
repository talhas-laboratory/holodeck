import re
import tomllib
from pathlib import Path


CANONICAL_REPOSITORY = "https://github.com/talhas-laboratory/holodeck"
LEGACY_SUFFIX_PATTERN = re.compile(r"holodeck[-_]runtime", re.IGNORECASE)


def test_public_repository_identity_is_canonical_and_unambiguous():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    readme = Path("README.md").read_text(encoding="utf-8")

    assert project["project"]["urls"]["Repository"] == CANONICAL_REPOSITORY
    assert CANONICAL_REPOSITORY in readme


def test_distribution_and_import_names_do_not_use_the_runtime_suffix():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["name"] == "holodeck-control-plane"
    assert "runtime" not in project["project"]["name"]
    assert project["project"]["scripts"]["holodeck"] == "holodeck_control_plane.cli:main"
    assert Path("src/holodeck_control_plane").is_dir()
    assert not Path("src/holodeck").exists()


def test_tracked_hidden_configuration_does_not_use_legacy_runtime_suffix():
    offenders: list[str] = []
    for path in Path(".").rglob("*"):
        if not path.is_file():
            continue
        if ".git/" in path.as_posix():
            continue
        if path.suffix in {".pyc", ".db"}:
            continue
        if "egg-info" in path.parts or ".venv" in path.parts:
            continue
        if path.name.startswith(".") or ".github" in path.parts:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if LEGACY_SUFFIX_PATTERN.search(text):
                offenders.append(path.as_posix())
    assert offenders == []
