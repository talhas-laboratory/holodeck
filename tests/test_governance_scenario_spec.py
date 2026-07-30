"""Governance scenario specification coverage tests (M1-002)."""

from __future__ import annotations

from pathlib import Path

from holodeck_governance.domain.catalogs import SCENARIO_CATALOG_EXPECTATIONS
from holodeck_governance.testing import (
    INFRASTRUCTURE_ONLY_PACKETS,
    PACKET_SCENARIO_OWNERS,
    ScenarioWorld,
    transactional_fault_points,
)

TASKS_DIR = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "work-to-be-done"
    / "taskboards"
    / "m1-governance-kernel"
    / "tasks"
)


def test_every_scenario_has_catalog_expectations() -> None:
    assert set(SCENARIO_CATALOG_EXPECTATIONS) == {f"GS-{i:03d}" for i in range(1, 15)}


def test_every_implementation_packet_declares_scenario_trace_or_infra() -> None:
    assert set(PACKET_SCENARIO_OWNERS) == {f"M1-{i:03d}" for i in range(1, 34)}
    owned = {
        scenario
        for scenarios in PACKET_SCENARIO_OWNERS.values()
        for scenario in scenarios
        if scenarios != PACKET_SCENARIO_OWNERS["M1-024"]
    }
    # Primary owners exclude the integrated proof packet's full set duplication check
    primary = {
        scenario
        for packet, scenarios in PACKET_SCENARIO_OWNERS.items()
        if packet != "M1-024"
        for scenario in scenarios
    }
    assert primary == {f"GS-{i:03d}" for i in range(1, 15)}
    assert "M1-001" in INFRASTRUCTURE_ONLY_PACKETS
    assert "M1-026" in INFRASTRUCTURE_ONLY_PACKETS
    assert owned  # silence lint if rewritten; primary covers all


def test_task_packets_reference_test_specification_when_behavioral() -> None:
    missing: list[str] = []
    for packet, scenarios in PACKET_SCENARIO_OWNERS.items():
        if not scenarios or packet == "M1-024":
            # M1-024 still should reference; checked below via glob presence
            pass
        matches = list(TASKS_DIR.glob(f"{packet}-*.md"))
        assert matches, f"missing task packet file for {packet}"
        text = matches[0].read_text(encoding="utf-8")
        if scenarios:
            if "m1-governance-test-specification" not in text and "Scenarios:" not in text:
                missing.append(packet)
    assert missing == []


def test_fixture_world_is_deterministic() -> None:
    left = ScenarioWorld()
    right = ScenarioWorld()
    assert left.ids.tenant_alpha == right.ids.tenant_alpha
    assert left.clock == right.clock
    assert "before_receipt_write" in transactional_fault_points()
    assert len(transactional_fault_points()) >= 6
