from holodeck_runtime.store import Store


def test_store_creates_workspace_task_and_non_overlapping_run(tmp_path):
    store = Store(tmp_path / "runtime.db")
    workspace = store.create_workspace({"workspace_id": "demo", "goal": "Ship safely."})
    task = store.create_task("demo", {"title": "Add endpoint", "status": "ready"})
    run = store.begin_run("demo", {"task_id": task["task_id"], "agent_id": "codex", "claimed_paths": ["src/api.py"]})
    assert workspace["workspace_id"] == "demo"
    assert run["status"] == "active"
