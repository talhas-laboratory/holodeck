from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_POLICY = {
    "read_repository": "automatic",
    "workspace_state": "automatic",
    "repository_write": "approval_required",
    "dependency_install": "approval_required",
    "network_access": "approval_required",
    "git_push": "approval_required",
    "deploy": "approval_required",
    "destructive_command": "denied",
}


def initialize_project(path: str | Path, *, force: bool = False) -> dict[str, Any]:
    root = Path(path).resolve()
    if not (root / ".git").exists():
        raise ValueError("Holodeck initialization requires a Git repository")
    directory = root / ".holodeck"
    manifest_path = directory / "manifest.json"
    policy_path = directory / "policy.json"
    if (manifest_path.exists() or policy_path.exists()) and not force:
        raise ValueError(".holodeck already exists; pass --force to replace its generated configuration")
    directory.mkdir(exist_ok=True)
    manifest = {
        "schema_version": "1.0",
        "project_root": ".",
        "workspace_id": root.name,
        "artifact_roots": ["."],
        "generated_by": "holodeck-runtime",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    policy_path.write_text(json.dumps({"schema_version": "1.0", "actions": DEFAULT_POLICY}, indent=2) + "\n", encoding="utf-8")
    return {"project_root": str(root), "manifest": str(manifest_path), "policy": str(policy_path)}


def policy_decision(path: str | Path, action: str) -> str:
    policy_path = Path(path).resolve() / ".holodeck" / "policy.json"
    if not policy_path.is_file():
        raise ValueError("no .holodeck policy found; run `holodeck init` first")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    return str(policy.get("actions", {}).get(action, "approval_required"))
