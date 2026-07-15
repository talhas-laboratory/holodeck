from holodeck_runtime.store import Store
from holodeck_runtime.project import initialize_project, policy_decision
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from holodeck_runtime.service import Handler


def test_store_creates_workspace_task_and_non_overlapping_run(tmp_path):
    store = Store(tmp_path / "runtime.db")
    workspace = store.create_workspace({"workspace_id": "demo", "goal": "Ship safely."})
    task = store.create_task("demo", {"title": "Add endpoint", "status": "ready"})
    run = store.begin_run("demo", {"task_id": task["task_id"], "agent_id": "codex", "claimed_paths": ["src/api.py"]})
    assert workspace["workspace_id"] == "demo"
    assert run["status"] == "active"
    assert store.runs("demo")[0]["run_id"] == run["run_id"]
    assert store.claims("demo")[0]["status"] == "active"
    assert store.claims("demo")[0]["task_id"] == task["task_id"]

    completed = store.complete_run("demo", run["run_id"], {"summary": "Endpoint shipped."})
    assert completed["status"] == "completed"
    assert completed["summary"] == "Endpoint shipped."
    assert store.claims("demo")[0]["status"] == "released"


def test_store_updates_complete_workspace_and_task_records(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    workspace = store.update_workspace(
        "demo",
        {"goal": "Operate safely", "artifact_roots": ["src", "tests"], "scope_out": ["production"]},
    )
    task = store.create_task("demo", {"task_id": "HD-001", "title": "First task"})
    task = store.update_task(
        "demo",
        task["task_id"],
        {"status": "review", "acceptance_criteria": ["Tests pass"], "constraints": ["No network"]},
    )
    assert workspace["scope_out"] == ["production"]
    assert task["status"] == "review"
    assert task["acceptance_criteria"] == ["Tests pass"]


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
    script = files("holodeck_runtime").joinpath("frontend/app.js").read_text(encoding="utf-8")
    assert "Holodeck — Autonomous Development Control Plane" in page
    assert "conversation os" not in page.lower()
    assert ".dialog-close, .dialog-actions [value=\"cancel\"]" in script


def test_http_control_plane_exposes_config_and_full_run_lifecycle(tmp_path):
    store = Store(tmp_path / "runtime.db")
    handler = type("TestHandler", (Handler,), {"store": store, "runtime_host": "127.0.0.1", "runtime_port": 0})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(path, *, method="GET", payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        with urlopen(req) as response:
            return json.loads(response.read())

    try:
        config = request("/api/config")
        assert config["onboarding_policy"]["actions"]["destructive_command"] == "denied"
        request("/api/workspaces", method="POST", payload={"workspace_id": "demo", "goal": "Ship"})
        request("/api/workspaces/demo", method="PATCH", payload={"scope_out": ["production"]})
        task = request("/api/workspaces/demo/tasks", method="POST", payload={"task_id": "HD-001", "title": "Build UI"})
        request(f"/api/workspaces/demo/tasks/{task['task_id']}", method="PATCH", payload={"status": "ready"})
        run = request("/api/workspaces/demo/runs", method="POST", payload={"task_id": task["task_id"], "agent_id": "codex", "claimed_paths": ["src"]})
        assert request("/api/workspaces/demo/claims")["claims"][0]["status"] == "active"
        request(f"/api/workspaces/demo/runs/{run['run_id']}/complete", method="POST", payload={"summary": "Done"})
        assert request("/api/workspaces/demo/runs")["runs"][0]["status"] == "completed"
        assert request("/api/workspaces/demo/claims")["claims"][0]["status"] == "released"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
