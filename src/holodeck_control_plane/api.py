from __future__ import annotations

from importlib.resources import files

from holodeck_control_plane.http_request import MAX_BODY_BYTES

API_VERSION = "1"
API_STABILITY = "alpha"
API_CONTRACT = "http-api-v1"
DOCUMENTATION_PATH = "/docs/http-api-v1"
MCP_SETUP_PATH = "/docs/mcp-setup"
SUPPORTED_API_VERSIONS = frozenset({API_VERSION})


def packaged_documentation_path(name: str) -> str:
    """Return a package resource path for a bundled documentation file."""
    resource = files("holodeck_control_plane").joinpath("docs", name)
    if not resource.is_file():
        raise FileNotFoundError(f"packaged documentation missing: {name}")
    return str(resource)


def api_config_section() -> dict[str, str | int]:
    """Machine-readable API contract identity exposed at GET /api/config."""
    return {
        "version": API_VERSION,
        "stability": API_STABILITY,
        "contract": API_CONTRACT,
        "documentation": DOCUMENTATION_PATH,
        "mcp_setup": MCP_SETUP_PATH,
        "max_json_body_bytes": MAX_BODY_BYTES,
        "breaking_change_policy": (
            "Incompatible request or response changes require incrementing api.version. "
            "Additive fields may appear without a version bump during the alpha stability window."
        ),
    }
