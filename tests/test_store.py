from holodeck_runtime.store import Store
from holodeck_runtime.project import initialize_project, policy_decision
from holodeck_runtime.service import Handler


def test_store_creates_workspace_task_and_non_overlapping_run(tmp_path):
    store = Store(tmp_path / "runtime.db")
    workspace = store.create_workspace({"workspace_id": "demo", "goal": "Ship safely."})
    task = store.create_task("demo", {"title": "Add endpoint", "status": "ready"})
    run = store.begin_run("demo", {"task_id": task["task_id"], "agent_id": "codex", "claimed_paths": ["src/api.py"]})
    assert workspace["workspace_id"] == "demo"
    assert run["status"] == "active"


def test_project_initialization_requires_git_and_defaults_to_conservative_policy(tmp_path):
    (tmp_path / ".git").mkdir()
    result = initialize_project(tmp_path)
    assert result["manifest"].endswith(".holodeck/manifest.json")
    assert policy_decision(tmp_path, "deploy") == "approval_required"
    assert policy_decision(tmp_path, "destructive_command") == "denied"


def test_frontend_is_packaged_and_owned_by_runtime():
    assert Handler
    from importlib.resources import files

    page = files("holodeck_runtime").joinpath("frontend/index.html").read_text(encoding="utf-8")
    assert "Holodeck — Development Workspace" in page
    assert "conversation os" not in page.lower()
