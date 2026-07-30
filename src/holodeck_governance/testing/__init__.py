"""Deterministic fixture builders for M1 governance scenarios.

Builders construct only the records a test needs. IDs, timestamps, and hashes
must be stable for a given seed. Persistence wiring lands with repository
packets; this module defines the fixture world contract used by GS tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final


FIXED_CLOCK: Final = datetime(2026, 7, 24, 12, 0, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class FixtureIds:
    """Stable opaque IDs for the canonical fixture world."""

    tenant_alpha: str = "01900000-0000-7000-8000-000000000001"
    tenant_beta: str = "01900000-0000-7000-8000-000000000002"
    workspace_alpha_1: str = "01900000-0000-7000-8000-000000000011"
    workspace_beta_1: str = "01900000-0000-7000-8000-000000000012"
    human_owner: str = "01900000-0000-7000-8000-000000000021"
    human_reviewer: str = "01900000-0000-7000-8000-000000000022"
    worker_agent: str = "01900000-0000-7000-8000-000000000023"
    system_service: str = "01900000-0000-7000-8000-000000000024"
    mission_object: str = "01900000-0000-7000-8000-000000000031"
    requirement_object: str = "01900000-0000-7000-8000-000000000032"
    test_plan_object: str = "01900000-0000-7000-8000-000000000033"


@dataclass(slots=True)
class ScenarioWorld:
    """Composable fixture world; tests opt into subsets."""

    ids: FixtureIds = field(default_factory=FixtureIds)
    clock: datetime = FIXED_CLOCK
    notes: list[str] = field(default_factory=list)


# Packet → owned scenarios (primary). Infrastructure-only packets list empty.
PACKET_SCENARIO_OWNERS: Final[dict[str, tuple[str, ...]]] = {
    "M1-001": (),
    "M1-002": (),
    "M1-003": ("GS-001",),
    "M1-004": (),
    "M1-005": ("GS-002",),
    "M1-006": (),
    "M1-007": (),
    "M1-008": (),
    "M1-009": ("GS-005",),
    "M1-010": (),
    "M1-011": (),
    "M1-012": ("GS-004",),
    "M1-013": ("GS-006",),
    "M1-014": ("GS-011",),
    "M1-015": ("GS-007",),
    "M1-016": (),
    "M1-017": ("GS-008",),
    "M1-018": ("GS-003", "GS-009"),
    "M1-019": (),
    "M1-020": ("GS-010",),
    "M1-021": ("GS-012",),
    "M1-022": ("GS-013",),
    "M1-023": ("GS-014",),
    "M1-024": tuple(f"GS-{i:03d}" for i in range(1, 15)),
    "M1-025": (),
    "M1-026": (),
    "M1-027": (),
    "M1-028": (),
    "M1-029": (),
    "M1-030": (),
    "M1-031": (),
    "M1-032": ("GS-001",),
    "M1-033": ("GS-001", "GS-004"),
}

INFRASTRUCTURE_ONLY_PACKETS: Final[frozenset[str]] = frozenset(
    packet for packet, scenarios in PACKET_SCENARIO_OWNERS.items() if not scenarios
)


def transactional_fault_points() -> tuple[str, ...]:
    """Named write boundaries for GS-010 fault injection."""

    return (
        "before_receipt_write",
        "after_receipt_before_evaluation",
        "after_evaluation_before_transition",
        "after_transition_before_event",
        "after_event_before_outbox",
        "after_outbox_before_commit",
    )
