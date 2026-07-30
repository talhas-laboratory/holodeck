#!/usr/bin/env python3
"""Regenerate tracked M2 code-graph acceptance metrics intentionally.

Runs the acceptance/incremental metric tests with
``HOLODECK_UPDATE_ACCEPTANCE_ARTIFACTS=1`` so volatile run artifacts are
copied into ``artifacts/``. Evidence markdown must still be stamped to the
exact reviewed commit separately.
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    env = os.environ.copy()
    env["HOLODECK_UPDATE_ACCEPTANCE_ARTIFACTS"] = "1"
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_m2_code_graph_acceptance.py::test_m2_026_factual_graph_lifecycle_acceptance",
        "tests/test_m2_code_graph_incremental_refresh.py::test_incremental_matches_full_normalized_facts_on_golden",
    ]
    print(" ".join(cmd))
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
