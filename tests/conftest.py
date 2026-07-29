"""Pytest configuration for Holodeck tests."""

from __future__ import annotations

from pathlib import Path

# Fixture repositories under tests/fixtures contain realistic test_*.py files
# that must not be collected as Holodeck suite modules.
collect_ignore_glob = [
    "fixtures/*",
    "fixtures/**/*",
]

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def pytest_ignore_collect(collection_path: Path, config) -> bool:  # noqa: ARG001
    try:
        collection_path.resolve().relative_to(_FIXTURE_ROOT.resolve())
    except ValueError:
        return False
    return True
