"""Helpers for the Python reference factual-graph fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parent
TREES_ROOT = FIXTURE_ROOT / "trees"
REVISIONS_PATH = FIXTURE_ROOT / "revisions.json"


def iter_tree_files(tree_root: Path) -> tuple[Path, ...]:
    files = [
        path
        for path in sorted(tree_root.rglob("*"))
        if path.is_file() and path.name != ".DS_Store"
    ]
    return tuple(files)


def content_hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_revision_hash(tree_root: Path) -> str:
    """Deterministic content identity for one fixture tree."""

    digest = hashlib.sha256()
    root = tree_root.resolve()
    for path in iter_tree_files(root):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def fixture_revision_id(tree_name: str) -> str:
    return f"fixture:{tree_revision_hash(TREES_ROOT / tree_name)}"


def changed_paths(rev_a: Path, rev_b: Path) -> tuple[str, ...]:
    a_files = {
        path.relative_to(rev_a).as_posix(): content_hash_file(path)
        for path in iter_tree_files(rev_a)
    }
    b_files = {
        path.relative_to(rev_b).as_posix(): content_hash_file(path)
        for path in iter_tree_files(rev_b)
    }
    changed = sorted(
        path
        for path in sorted(set(a_files) | set(b_files))
        if a_files.get(path) != b_files.get(path)
    )
    return tuple(changed)


def write_revisions_manifest() -> dict[str, object]:
    rev_a = TREES_ROOT / "rev_a"
    rev_b = TREES_ROOT / "rev_b"
    payload = {
        "schema_version": "m2.code_graph_fixture_revisions.v1",
        "revisions": {
            "rev_a": {
                "tree": "trees/rev_a",
                "repository_revision": fixture_revision_id("rev_a"),
                "tree_sha256": tree_revision_hash(rev_a),
            },
            "rev_b": {
                "tree": "trees/rev_b",
                "repository_revision": fixture_revision_id("rev_b"),
                "tree_sha256": tree_revision_hash(rev_b),
                "changed_paths_from_rev_a": list(changed_paths(rev_a, rev_b)),
            },
        },
        "unresolved_dynamic_call": {
            "path": "sample_app/service.py",
            "symbol": "Greeter.invoke",
            "diagnostic_code": "unresolved_dynamic_call",
        },
    }
    REVISIONS_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    print(json.dumps(write_revisions_manifest(), indent=2, sort_keys=True))
