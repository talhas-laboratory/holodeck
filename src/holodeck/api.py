from __future__ import annotations

from holodeck.http_request import MAX_BODY_BYTES

API_VERSION = "1"
API_STABILITY = "alpha"
API_CONTRACT = "http-api-v1"
DOCUMENTATION_PATH = "docs/http-api-v1.md"


def api_config_section() -> dict[str, str | int]:
    """Machine-readable API contract identity exposed at GET /api/config."""
    return {
        "version": API_VERSION,
        "stability": API_STABILITY,
        "contract": API_CONTRACT,
        "documentation": DOCUMENTATION_PATH,
        "max_json_body_bytes": MAX_BODY_BYTES,
        "breaking_change_policy": (
            "Incompatible request or response changes require incrementing api.version. "
            "Additive fields may appear without a version bump during the alpha stability window."
        ),
    }
