"""Shared workspace-intelligence enums and contractual constants."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

# Permission required to curate governed workspace intelligence records.
INTELLIGENCE_CURATE_PERMISSION: Final = "workspace.intelligence.curate"

# Contractual M2 command types submitted through GovernanceApplicationService.
M2_COMMAND_INTELLIGENCE_ONBOARD: Final = "workspace.intelligence.onboard"
M2_COMMAND_INTELLIGENCE_REFRESH: Final = "workspace.intelligence.refresh"
M2_COMMAND_MODEL_PROPOSE: Final = "workspace.model.propose"
M2_COMMAND_MODEL_APPROVE: Final = "workspace.model.approve"
M2_COMMAND_SOURCE_REGISTER: Final = "workspace.source.register"
M2_COMMAND_CONTEXT_MODULE_APPROVE: Final = "workspace.context_module.approve"
M2_COMMAND_KNOWLEDGE_GAP_RESOLVE: Final = "workspace.knowledge_gap.resolve"
M2_COMMAND_READINESS_ASSESS: Final = "workspace.readiness.assess"

M2_INTELLIGENCE_COMMAND_TYPES: Final[frozenset[str]] = frozenset(
    {
        M2_COMMAND_INTELLIGENCE_ONBOARD,
        M2_COMMAND_INTELLIGENCE_REFRESH,
        M2_COMMAND_MODEL_PROPOSE,
        M2_COMMAND_MODEL_APPROVE,
        M2_COMMAND_SOURCE_REGISTER,
        M2_COMMAND_CONTEXT_MODULE_APPROVE,
        M2_COMMAND_KNOWLEDGE_GAP_RESOLVE,
        M2_COMMAND_READINESS_ASSESS,
    }
)

M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED: Final = (
    "workspace.intelligence.onboarding_requested"
)
M2_EVENT_MODEL_PROPOSED: Final = "workspace.model.proposed"
M2_EVENT_MODEL_APPROVED: Final = "workspace.model.approved"
M2_EVENT_SOURCE_REGISTERED: Final = "workspace.source.registered"
M2_EVENT_SOURCE_STALE: Final = "workspace.source.stale"
M2_EVENT_CONTEXT_MODULE_STALE: Final = "workspace.context_module.stale"
M2_EVENT_KNOWLEDGE_GAP_CREATED: Final = "workspace.knowledge_gap.created"
M2_EVENT_READINESS_ASSESSED: Final = "workspace.readiness.assessed"

REQUIRED_MODEL_SECTIONS: Final[tuple[str, ...]] = (
    "identity_and_purpose",
    "stakeholders_actors_authority",
    "product_and_domain_model",
    "architecture_and_system_map",
    "engineering_principles_and_constraints",
    "domain_language",
    "decisions_contradictions_and_gaps",
)

STANDARD_CONTEXT_MODULE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "core-principles",
        "product-and-users",
        "architecture",
        "data-and-persistence",
        "testing-and-verification",
        "security-and-authority",
        "operations-and-release",
        "domain-language",
        "decisions-and-history",
    }
)


class ModelRevisionStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class SectionCertainty(StrEnum):
    """Per-section certainty; unknown/disputed must remain explicit."""

    CONFIRMED = "confirmed"
    PROPOSED = "proposed"
    UNKNOWN = "unknown"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"


class SourceType(StrEnum):
    REPOSITORY_FILE = "repository_file"
    DOCUMENT = "document"
    API = "api"
    HUMAN_INPUT = "human_input"
    TASK_HISTORY = "task_history"
    RUNTIME_OBSERVATION = "runtime_observation"
    TEST_RESULT = "test_result"
    GENERATED_INTERPRETATION = "generated_interpretation"


class TrustClass(StrEnum):
    INSTRUCTION_AUTHORITY = "instruction_authority"
    AUTHORITATIVE_REFERENCE = "authoritative_reference"
    TRUSTED_OBSERVATION = "trusted_observation"
    ORDINARY_REFERENCE = "ordinary_reference"
    UNTRUSTED_REFERENCE = "untrusted_reference"
    GENERATED_INTERPRETATION = "generated_interpretation"


class StaleStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class ContextItemType(StrEnum):
    SOURCE_FACT = "source_fact"
    APPROVED_INSTRUCTION = "approved_instruction"
    WORKSPACE_RULE = "workspace_rule"
    GENERATED_SUMMARY = "generated_summary"
    ASSUMPTION = "assumption"
    OPEN_QUESTION = "open_question"
    CONFLICT = "conflict"
    DECISION = "decision"
    RUNTIME_OBSERVATION = "runtime_observation"
    INCIDENT_LEARNING = "incident_learning"


class ValidationStatus(StrEnum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class ModuleApprovalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class GapStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    ACCEPTED_UNKNOWN = "accepted_unknown"


class ContradictionStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


class DecisionOutcome(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class ReadinessLevel(StrEnum):
    """Evidence-backed readiness; higher levels require more approved authority."""

    UNINTERPRETED = "0_uninterpreted"
    DISCOVERED = "1_discovered"
    CONTEXTUALIZED = "2_contextualized"
    GOVERNED = "3_governed"
    VERIFIABLE = "4_verifiable"
    OPERATIONALLY_ASSURED = "5_operationally_assured"


READINESS_LEVEL_ORDER: Final[tuple[ReadinessLevel, ...]] = (
    ReadinessLevel.UNINTERPRETED,
    ReadinessLevel.DISCOVERED,
    ReadinessLevel.CONTEXTUALIZED,
    ReadinessLevel.GOVERNED,
    ReadinessLevel.VERIFIABLE,
    ReadinessLevel.OPERATIONALLY_ASSURED,
)

READINESS_PERMITTED_CAPABILITY: Final[dict[ReadinessLevel, str]] = {
    ReadinessLevel.UNINTERPRETED: "browsing_and_summarization",
    ReadinessLevel.DISCOVERED: "explanation_and_limited_suggestions",
    ReadinessLevel.CONTEXTUALIZED: "planning_and_supervised_proposals",
    ReadinessLevel.GOVERNED: "bounded_controlled_execution",
    ReadinessLevel.VERIFIABLE: "autonomous_acceptance_for_approved_risk",
    ReadinessLevel.OPERATIONALLY_ASSURED: "highly_autonomous_lanes_where_policy_permits",
}

# Trust ranks used to reject silent escalation into instruction authority.
TRUST_RANK: Final[dict[TrustClass, int]] = {
    TrustClass.UNTRUSTED_REFERENCE: 0,
    TrustClass.GENERATED_INTERPRETATION: 1,
    TrustClass.ORDINARY_REFERENCE: 2,
    TrustClass.TRUSTED_OBSERVATION: 3,
    TrustClass.AUTHORITATIVE_REFERENCE: 4,
    TrustClass.INSTRUCTION_AUTHORITY: 5,
}
