"""Canonical workspace-intelligence scenario expectations (WIS-001..006)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from holodeck_governance.domain.workspace.intelligence.types import (
    M2_COMMAND_CONTEXT_MODULE_APPROVE,
    M2_COMMAND_INTELLIGENCE_ONBOARD,
    M2_COMMAND_INTELLIGENCE_REFRESH,
    M2_COMMAND_KNOWLEDGE_GAP_RESOLVE,
    M2_COMMAND_MODEL_APPROVE,
    M2_COMMAND_MODEL_PROPOSE,
    M2_COMMAND_READINESS_ASSESS,
    M2_COMMAND_SOURCE_REGISTER,
    M2_EVENT_CONTEXT_MODULE_STALE,
    M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED,
    M2_EVENT_KNOWLEDGE_GAP_CREATED,
    M2_EVENT_MODEL_APPROVED,
    M2_EVENT_MODEL_PROPOSED,
    M2_EVENT_READINESS_ASSESSED,
    M2_EVENT_SOURCE_REGISTERED,
    M2_EVENT_SOURCE_STALE,
)


@dataclass(frozen=True, slots=True)
class WorkspaceIntelligenceScenarioExpectation:
    scenario_id: str
    guarantee: str
    expected_records: tuple[str, ...]
    expected_events: tuple[str, ...]
    absent_writes: tuple[str, ...]
    m1_command_types: tuple[str, ...]
    summary: str


WIS_EXPECTATIONS: Final[dict[str, WorkspaceIntelligenceScenarioExpectation]] = {
    "WIS-001": WorkspaceIntelligenceScenarioExpectation(
        scenario_id="WIS-001",
        guarantee="onboarding_creates_versioned_intelligence",
        expected_records=(
            "workspace_model_revision",
            "workspace_source",
            "context_module",
            "knowledge_gap",
            "workspace_readiness_assessment",
        ),
        expected_events=(
            M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED,
            M2_EVENT_MODEL_PROPOSED,
            M2_EVENT_SOURCE_REGISTERED,
            M2_EVENT_KNOWLEDGE_GAP_CREATED,
            M2_EVENT_READINESS_ASSESSED,
        ),
        absent_writes=(
            "instruction_authority_without_approval",
            "mission",
            "run",
            "acceptance",
        ),
        m1_command_types=(
            M2_COMMAND_INTELLIGENCE_ONBOARD,
            M2_COMMAND_MODEL_PROPOSE,
            M2_COMMAND_SOURCE_REGISTER,
            M2_COMMAND_READINESS_ASSESS,
        ),
        summary="Onboarding yields a versioned model, sources, modules/gaps, and readiness.",
    ),
    "WIS-002": WorkspaceIntelligenceScenarioExpectation(
        scenario_id="WIS-002",
        guarantee="no_silent_instruction_authority",
        expected_records=("workspace_source:untrusted_or_generated",),
        expected_events=(),
        absent_writes=(
            "instruction_authority_without_approval",
            "approved_instruction_from_generated_summary",
        ),
        m1_command_types=(),
        summary="Untrusted/generated content cannot become instruction authority silently.",
    ),
    "WIS-003": WorkspaceIntelligenceScenarioExpectation(
        scenario_id="WIS-003",
        guarantee="generated_summary_provenance",
        expected_records=("context_item:generated_summary",),
        expected_events=(),
        absent_writes=("instruction_authority_on_generated_summary",),
        m1_command_types=(),
        summary="Generated summaries carry confidence and exact source revisions.",
    ),
    "WIS-004": WorkspaceIntelligenceScenarioExpectation(
        scenario_id="WIS-004",
        guarantee="selective_stale_propagation",
        expected_records=(
            "workspace_source:stale",
            "context_module:dependent_stale",
        ),
        expected_events=(
            M2_EVENT_SOURCE_STALE,
            M2_EVENT_CONTEXT_MODULE_STALE,
        ),
        absent_writes=("unrelated_module:stale",),
        m1_command_types=(M2_COMMAND_INTELLIGENCE_REFRESH,),
        summary="A source change stales only dependent modules.",
    ),
    "WIS-005": WorkspaceIntelligenceScenarioExpectation(
        scenario_id="WIS-005",
        guarantee="contradictions_remain_visible",
        expected_records=("contradiction:open",),
        expected_events=(),
        absent_writes=("silent_contradiction_collapse",),
        m1_command_types=(M2_COMMAND_KNOWLEDGE_GAP_RESOLVE,),
        summary="Contradictions remain visible until a recorded resolution.",
    ),
    "WIS-006": WorkspaceIntelligenceScenarioExpectation(
        scenario_id="WIS-006",
        guarantee="readiness_bounded_by_evidence",
        expected_records=("workspace_readiness_assessment",),
        expected_events=(
            M2_EVENT_MODEL_APPROVED,
            M2_EVENT_READINESS_ASSESSED,
        ),
        absent_writes=(
            "readiness_above_evidence",
            "governed_readiness_with_open_gaps",
        ),
        m1_command_types=(
            M2_COMMAND_MODEL_APPROVE,
            M2_COMMAND_CONTEXT_MODULE_APPROVE,
            M2_COMMAND_READINESS_ASSESS,
        ),
        summary="Readiness cannot exceed approved authority and available evidence.",
    ),
}


def required_intelligence_scenario_ids() -> tuple[str, ...]:
    return tuple(f"WIS-{index:03d}" for index in range(1, 7))
