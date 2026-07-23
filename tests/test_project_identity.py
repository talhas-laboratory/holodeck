import tomllib
from pathlib import Path


CANONICAL_REPOSITORY = "https://github.com/talhas-laboratory/holodeck"


def test_public_repository_identity_is_canonical_and_unambiguous():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    readme = Path("README.md").read_text(encoding="utf-8")

    assert project["project"]["urls"]["Repository"] == CANONICAL_REPOSITORY
    assert CANONICAL_REPOSITORY in readme


def test_distribution_and_import_names_do_not_use_the_runtime_suffix():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["name"] == "holodeck-control-plane"
    assert "runtime" not in project["project"]["name"]
    assert project["project"]["scripts"]["holodeck"] == "holodeck.cli:main"
    assert Path("src/holodeck").is_dir()
