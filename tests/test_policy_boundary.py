import subprocess
import sys
from pathlib import Path


def test_policy_boundary_is_advisory_in_cli_and_user_facing_copy():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from holodeck_control_plane.cli import main; main()",
            "policy-check",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    readme = Path("README.md").read_text(encoding="utf-8").lower()
    dashboard = Path("src/holodeck_control_plane/frontend/index.html").read_text(encoding="utf-8").lower()

    assert "advisory" in result.stdout.lower()
    assert "does not currently intercept, enforce, or block" in readme
    assert "advisory" in dashboard
