"""Fail-closed repository revision resolution for factual extractors.

Git checkouts (including worktrees where ``.git`` is a file) are resolved via
``git rev-parse``. Fixture trees use content hashes. Arbitrary directories never
echo the caller-supplied revision.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeGraphReason,
    code_graph_error,
)

_SKIP_DIR_NAMES = frozenset(
    {".git", "__pycache__", ".venv", "venv", ".tox", ".mypy_cache"}
)


def tree_content_hash(root: Path) -> str:
    """Deterministic content hash for offline fixture trees."""

    digest = hashlib.sha256()
    for path in _iter_hashed_files(root):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_actual_revision(root: Path, requested: str) -> str:
    """Return the checkout's actual immutable revision.

    Resolution policy (fail-closed):

    - ``fixture:<hash>`` requests must match ``fixture:<tree_content_hash>``.
    - Git repositories (regular or worktree) resolve ``HEAD`` through
      ``git rev-parse --verify HEAD`` and must have a clean worktree.
    - Anything else raises ``REVISION_MISMATCH`` — never trust the caller.
    """

    root = root.resolve()
    if not root.is_dir():
        raise code_graph_error(
            CodeGraphReason.MALFORMED_FACT,
            "repository_path must be an existing directory",
        )

    if requested.startswith("fixture:"):
        actual = f"fixture:{tree_content_hash(root)}"
        if actual != requested:
            raise code_graph_error(
                CodeGraphReason.REVISION_MISMATCH,
                "fixture content hash does not match requested_revision",
            )
        return actual

    if _is_git_checkout(root):
        actual = _git_rev_parse_head(root)
        if actual != requested:
            raise code_graph_error(
                CodeGraphReason.REVISION_MISMATCH,
                "git HEAD does not match requested_revision",
            )
        _require_clean_git_worktree(root)
        return actual

    raise code_graph_error(
        CodeGraphReason.REVISION_MISMATCH,
        "repository_path is not a git checkout or fixture tree; "
        "refusing to accept caller-supplied revision",
    )


def _is_git_checkout(root: Path) -> bool:
    git = root / ".git"
    # Worktrees use a `.git` *file* pointing at the common git dir.
    return git.is_dir() or git.is_file()


def _git_rev_parse_head(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise code_graph_error(
            CodeGraphReason.REVISION_MISMATCH,
            f"unable to resolve git HEAD: {exc}",
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise code_graph_error(
            CodeGraphReason.REVISION_MISMATCH,
            f"git rev-parse HEAD failed: {detail or completed.returncode}",
        )
    revision = completed.stdout.strip()
    if len(revision) < 7:
        raise code_graph_error(
            CodeGraphReason.REVISION_MISMATCH,
            "git rev-parse HEAD returned an empty or short revision",
        )
    return revision


def _require_clean_git_worktree(root: Path) -> None:
    """Reject modified or untracked files before reading a Git checkout.

    The Python extractor reads paths from the worktree.  ``HEAD`` alone is not
    evidence that those bytes are the requested commit: a dirty checkout can
    contain modified tracked files or arbitrary untracked files.  M2 therefore
    requires a clean repository-bound execution workspace until a later
    adapter reads Git objects directly.
    """

    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise code_graph_error(
            CodeGraphReason.REVISION_MISMATCH,
            f"unable to verify git worktree cleanliness: {exc}",
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise code_graph_error(
            CodeGraphReason.REVISION_MISMATCH,
            f"git status failed: {detail or completed.returncode}",
        )
    if completed.stdout.strip():
        raise code_graph_error(
            CodeGraphReason.REVISION_MISMATCH,
            "repository worktree is dirty; extraction requires exact committed bytes",
        )


def _iter_hashed_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        files.append(path)
    return tuple(files)
