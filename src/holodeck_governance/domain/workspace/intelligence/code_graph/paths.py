"""Repository path and revision validators for factual code-graph facts."""

from __future__ import annotations

import re

from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    CodeGraphReason,
    REJECTED_REVISION_NAMES,
    code_graph_error,
)

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_HEX_REVISION = re.compile(r"^[0-9a-f]{7,64}$")
_FIXTURE_REVISION = re.compile(r"^fixture:[0-9a-f]{8,64}$")


def normalize_repository_relative_path(path: str) -> str:
    """Normalize and validate a repository-relative POSIX path.

    Absolute paths, empty paths, parent traversal, and blank segments are
    rejected at the domain boundary.
    """

    if not isinstance(path, str) or not path.strip():
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT, "repository_relative_path is required"
        )
    raw = path.strip().replace("\\", "/")
    if raw.startswith("/") or _WINDOWS_DRIVE.match(raw) or raw.startswith("//"):
        raise code_graph_error(
            CodeGraphReason.ABSOLUTE_PATH,
            "absolute paths are rejected at the code-graph boundary",
        )
    if raw in {".", "./"}:
        return "."
    if raw.startswith("./"):
        raw = raw[2:]
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts:
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT,
            "repository_relative_path must contain at least one path segment",
        )
    if any(part == ".." for part in parts):
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT,
            "repository_relative_path must not contain parent traversal",
        )
    return "/".join(parts)


def require_immutable_repository_revision(revision: str) -> str:
    """Accept only immutable content identities, never mutable branch names."""

    if not isinstance(revision, str) or not revision.strip():
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT, "repository_revision is required"
        )
    value = revision.strip()
    lowered = value.lower()
    if lowered in REJECTED_REVISION_NAMES or lowered.startswith("refs/"):
        raise code_graph_error(
            CodeGraphReason.MUTABLE_REVISION,
            "mutable branch or ref names are not repository revisions",
        )
    if _HEX_REVISION.fullmatch(lowered) or _FIXTURE_REVISION.fullmatch(lowered):
        return lowered
    raise code_graph_error(
        CodeGraphReason.MUTABLE_REVISION,
        "repository_revision must be a content hash or fixture:<hash>",
    )
