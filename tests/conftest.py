"""Pytest configuration for Holodeck tests."""

from __future__ import annotations

# Fixture repositories under tests/fixtures contain realistic test_*.py files
# that must not be collected as Holodeck suite modules.
collect_ignore_glob = [
    "fixtures/*",
    "fixtures/**/*",
]
