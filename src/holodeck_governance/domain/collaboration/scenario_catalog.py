"""Canonical collaboration intake scenario expectations (CIS-001..008)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from holodeck_governance.domain.collaboration.types import (
    M2_COMMAND_ORIGIN_RECORD,
    M2_COMMAND_OUTBOUND_ENQUEUE,
    M2_COMMAND_RECEIPT_RECORD,
    ProcessingOutcome,
)


@dataclass(frozen=True, slots=True)
class CollaborationScenarioExpectation:
    scenario_id: str
    guarantee: str
    processing_outcome: ProcessingOutcome
    expected_records: tuple[str, ...]
    expected_events: tuple[str, ...]
    expected_outbox_actions: tuple[str, ...]
    absent_writes: tuple[str, ...]
    m1_command_types: tuple[str, ...]
    summary: str


CIS_EXPECTATIONS: Final[dict[str, CollaborationScenarioExpectation]] = {
    "CIS-001": CollaborationScenarioExpectation(
        scenario_id="CIS-001",
        guarantee="authentication",
        processing_outcome=ProcessingOutcome.AUTH_FAILED,
        expected_records=(),
        expected_events=(),
        expected_outbox_actions=(),
        absent_writes=(
            "task_origin",
            "inbound_event_receipt",
            "success_outbox_item",
            "accepted_collaboration_command",
            "mission",
            "run",
            "approval",
            "acceptance",
        ),
        m1_command_types=(),
        summary="Unverified provider payload creates no Holodeck governed intake state.",
    ),
    "CIS-002": CollaborationScenarioExpectation(
        scenario_id="CIS-002",
        guarantee="authorization",
        processing_outcome=ProcessingOutcome.REJECTED,
        expected_records=(
            "external_reference:source_event",
            "inbound_event_receipt",
        ),
        expected_events=(
            "governance.command.received",
            "governance.command.rejected",
        ),
        expected_outbox_actions=(),
        absent_writes=(
            "task_origin",
            "success_outbox_item",
            "mission",
            "run",
            "approval",
            "acceptance",
        ),
        m1_command_types=(M2_COMMAND_RECEIPT_RECORD,),
        summary="Verified but unauthorized intake records a rejected receipt only.",
    ),
    "CIS-003": CollaborationScenarioExpectation(
        scenario_id="CIS-003",
        guarantee="duplicate_delivery",
        processing_outcome=ProcessingOutcome.DUPLICATE_REPLAY,
        expected_records=("inbound_event_receipt:prior",),
        expected_events=(),
        expected_outbox_actions=(),
        absent_writes=(
            "task_origin:second",
            "success_outbox_item:second",
            "mission",
            "run",
            "approval",
            "acceptance",
        ),
        m1_command_types=(),
        summary="Replayed external event returns the prior receipt without new side effects.",
    ),
    "CIS-004": CollaborationScenarioExpectation(
        scenario_id="CIS-004",
        guarantee="crash_retry",
        processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
        expected_records=(
            "external_reference:source_event",
            "inbound_event_receipt",
            "task_origin",
            "outbound_collaboration_message",
        ),
        expected_events=(
            "governance.command.received",
            "governance.command.accepted",
            "governance.outbox.enqueued",
        ),
        expected_outbox_actions=("enqueue_status:once",),
        absent_writes=(
            "task_origin:duplicate",
            "success_outbox_item:duplicate",
            "mission",
            "run",
            "approval",
            "acceptance",
        ),
        m1_command_types=(
            M2_COMMAND_RECEIPT_RECORD,
            M2_COMMAND_ORIGIN_RECORD,
            M2_COMMAND_OUTBOUND_ENQUEUE,
        ),
        summary="Crash/retry converges to one origin and one correlated status enqueue.",
    ),
    "CIS-005": CollaborationScenarioExpectation(
        scenario_id="CIS-005",
        guarantee="tenant_isolation",
        processing_outcome=ProcessingOutcome.REJECTED,
        expected_records=(
            "external_reference:source_event",
            "inbound_event_receipt",
        ),
        expected_events=(
            "governance.command.received",
            "governance.command.rejected",
        ),
        expected_outbox_actions=(),
        absent_writes=(
            "task_origin",
            "cross_tenant_row",
            "success_outbox_item",
            "mission",
            "run",
            "approval",
            "acceptance",
        ),
        m1_command_types=(M2_COMMAND_RECEIPT_RECORD,),
        summary="Cross-tenant intake references are rejected without Beta writes.",
    ),
    "CIS-006": CollaborationScenarioExpectation(
        scenario_id="CIS-006",
        guarantee="rejection_absence_non_intake",
        processing_outcome=ProcessingOutcome.IGNORED_NON_INTAKE,
        expected_records=(
            "external_reference:source_event",
            "inbound_event_receipt",
        ),
        expected_events=(
            "governance.command.received",
            "governance.command.accepted",
        ),
        expected_outbox_actions=(),
        absent_writes=(
            "task_origin",
            "success_outbox_item",
            "mission",
            "run",
            "approval",
            "acceptance",
        ),
        m1_command_types=(M2_COMMAND_RECEIPT_RECORD,),
        summary="Ordinary conversation is receipted as non-intake with no origin.",
    ),
    "CIS-007": CollaborationScenarioExpectation(
        scenario_id="CIS-007",
        guarantee="source_to_status_correlation",
        processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
        expected_records=(
            "external_reference:source_event",
            "inbound_event_receipt",
            "task_origin",
            "outbound_collaboration_message",
        ),
        expected_events=(
            "governance.command.received",
            "governance.command.accepted",
            "governance.outbox.enqueued",
        ),
        expected_outbox_actions=("enqueue_status:correlated",),
        absent_writes=(
            "uncorrelated_status",
            "mission",
            "run",
            "approval",
            "acceptance",
        ),
        m1_command_types=(
            M2_COMMAND_RECEIPT_RECORD,
            M2_COMMAND_ORIGIN_RECORD,
            M2_COMMAND_OUTBOUND_ENQUEUE,
        ),
        summary="Accepted intake enqueues status correlated to origin and receipt.",
    ),
    "CIS-008": CollaborationScenarioExpectation(
        scenario_id="CIS-008",
        guarantee="explicit_intake_boundary",
        processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
        expected_records=(
            "external_reference:source_event",
            "inbound_event_receipt",
            "task_origin",
            "outbound_collaboration_message",
        ),
        expected_events=(
            "governance.command.received",
            "governance.command.accepted",
            "governance.outbox.enqueued",
        ),
        expected_outbox_actions=("enqueue_status:correlated",),
        absent_writes=(
            "mission",
            "run",
            "approval",
            "acceptance",
            "requirement",
            "evidence",
        ),
        m1_command_types=(
            M2_COMMAND_RECEIPT_RECORD,
            M2_COMMAND_ORIGIN_RECORD,
            M2_COMMAND_OUTBOUND_ENQUEUE,
        ),
        summary="Explicit intake creates an origin only; never mission/run/approval.",
    ),
}


def required_scenario_ids() -> tuple[str, ...]:
    return tuple(f"CIS-{index:03d}" for index in range(1, 9))
