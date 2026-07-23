from __future__ import annotations

from holodeck_runtime.errors import ValidationError


def components_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    limit = min(len(left), len(right))
    return left[:limit] == right[:limit]


def normalize_path(raw: str) -> tuple[str, ...]:
    text = raw.strip()
    if not text:
        raise ValidationError("path is required")
    if "\\" in text:
        raise ValidationError("path must use forward slashes")
    if text.startswith("/"):
        raise ValidationError("path must be repository-relative")
    if len(text) >= 2 and text[0].isalpha() and text[1] == ":":
        raise ValidationError("path must be repository-relative")

    parts: list[str] = []
    for segment in text.split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            raise ValidationError("path must not traverse outside the repository")
        parts.append(segment)
    return tuple(parts)


def format_path(components: tuple[str, ...]) -> str:
    return "." if not components else "/".join(components)


def normalize_boundary_paths(values: list[str]) -> list[tuple[str, ...]]:
    return [normalize_path(value) for value in values if str(value).strip()]


def effective_artifact_roots(artifact_roots: list[str]) -> list[tuple[str, ...]]:
    if not artifact_roots:
        return []
    return normalize_boundary_paths(artifact_roots)


def is_descendant_or_equal(path: tuple[str, ...], root: tuple[str, ...]) -> bool:
    if len(path) < len(root):
        return False
    return path[: len(root)] == root


def paths_intersect(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return components_overlap(left, right)


def validate_claim_path(
    raw: str,
    *,
    artifact_roots: list[str],
    scope_out: list[str],
) -> str:
    claim = normalize_path(raw)
    roots = effective_artifact_roots(artifact_roots)
    if not any(is_descendant_or_equal(claim, root) for root in roots):
        raise ValidationError("claimed path is outside workspace artifact roots")
    for excluded in normalize_boundary_paths(scope_out):
        if paths_intersect(claim, excluded):
            raise ValidationError("claimed path intersects scope_out")
    return format_path(claim)
