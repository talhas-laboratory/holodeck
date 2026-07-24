import pytest

from holodeck_control_plane.errors import ValidationError
from holodeck_control_plane.store import Store


def test_governed_mission_requires_approved_source_linked_proposals_and_evidence(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    task = store.create_task("demo", {"task_id": "governed", "title": "Governed work"})
    source = store.create_source("demo", {"label": "Intent", "content": "Ship bounded work", "trust_class": "instruction_authority"})

    contract = store.propose("demo", task["task_id"], {"kind": "delegation_contract", "curator": "test-curator", "source_ids": [source["source_id"]], "proposal": {"intended_outcome": "Ship safely"}})
    requirement = store.propose("demo", task["task_id"], {"kind": "requirement", "curator": "test-curator", "source_ids": [source["source_id"]], "proposal": {"statement": "Evidence is required"}})

    with pytest.raises(ValidationError, match="approved proposals"):
        store.compile_mission("demo", task["task_id"], {"proposal_ids": [contract["proposal_id"], requirement["proposal_id"]]})

    store.approve_proposal("demo", task["task_id"], contract["proposal_id"])
    store.approve_proposal("demo", task["task_id"], requirement["proposal_id"])
    mission = store.compile_mission("demo", task["task_id"], {"proposal_ids": [contract["proposal_id"], requirement["proposal_id"]]})
    assert mission["status"] == "ready"
    assert len(mission["packet_hash"]) == 64

    with pytest.raises(ValidationError, match="evidence"):
        store.accept_mission("demo", task["task_id"], mission["mission_id"])

    store.add_evidence("demo", task["task_id"], mission["mission_id"], {"requirement_id": requirement["proposal_id"], "artifact": "pytest: passed"})
    decision = store.accept_mission("demo", task["task_id"], mission["mission_id"])
    assert decision["decision"] == "accepted"
    assert store.mission("demo", task["task_id"], mission["mission_id"])["status"] == "accepted"


def test_curator_proposal_rejects_unknown_workspace_source(tmp_path):
    store = Store(tmp_path / "runtime.db")
    store.create_workspace({"workspace_id": "demo"})
    store.create_task("demo", {"task_id": "governed", "title": "Governed work"})
    with pytest.raises(ValidationError, match="sources in this workspace"):
        store.propose("demo", "governed", {"kind": "requirement", "curator": "test-curator", "source_ids": ["source-missing"], "proposal": {"statement": "x"}})
