"""Workspace intelligence domain contracts (persistence deferred to M2-013+).

Must not import application, storage, adapters, sqlite3, HTTP, MCP, or provider SDKs.
"""

from __future__ import annotations

from holodeck_governance.domain.workspace.intelligence.catalog import (
    WIS_EXPECTATIONS,
    WorkspaceIntelligenceScenarioExpectation,
    required_intelligence_scenario_ids,
)
from holodeck_governance.domain.workspace.intelligence.context import (
    ContextItem,
    ContextModule,
)
from holodeck_governance.domain.workspace.intelligence.discovery import (
    DiscoveredSourceCandidate,
    ObservedSourcePath,
    classify_observed_path,
    invent_sources_from_observations,
    observed_path_for_classification,
)
from holodeck_governance.domain.workspace.intelligence.gaps import (
    Contradiction,
    KnowledgeGap,
    WorkspaceDecision,
)
from holodeck_governance.domain.workspace.intelligence.model import (
    IntentSeed,
    ModelSectionState,
    WorkspaceModelRevision,
    section_certainty_map,
)
from holodeck_governance.domain.workspace.intelligence.readiness import (
    WorkspaceReadinessAssessment,
    readiness_at_most,
    readiness_level_index,
)
from holodeck_governance.domain.workspace.intelligence.sources import (
    WorkspaceSource,
    workspace_source_dedupe_key,
)
from holodeck_governance.domain.workspace.intelligence.trust import (
    assert_trust_promotion_allowed,
)
from holodeck_governance.domain.workspace.intelligence.types import (
    INTELLIGENCE_CURATE_PERMISSION,
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
    M2_INTELLIGENCE_COMMAND_TYPES,
    READINESS_LEVEL_ORDER,
    READINESS_PERMITTED_CAPABILITY,
    REQUIRED_MODEL_SECTIONS,
    STANDARD_CONTEXT_MODULE_KEYS,
    TRUST_RANK,
    ContextItemType,
    ContradictionStatus,
    DecisionOutcome,
    GapStatus,
    ModelRevisionStatus,
    ModuleApprovalStatus,
    ReadinessLevel,
    SectionCertainty,
    SourceType,
    StaleStatus,
    TrustClass,
    ValidationStatus,
)

__all__ = [
    "INTELLIGENCE_CURATE_PERMISSION",
    "M2_COMMAND_CONTEXT_MODULE_APPROVE",
    "M2_COMMAND_INTELLIGENCE_ONBOARD",
    "M2_COMMAND_INTELLIGENCE_REFRESH",
    "M2_COMMAND_KNOWLEDGE_GAP_RESOLVE",
    "M2_COMMAND_MODEL_APPROVE",
    "M2_COMMAND_MODEL_PROPOSE",
    "M2_COMMAND_READINESS_ASSESS",
    "M2_COMMAND_SOURCE_REGISTER",
    "M2_EVENT_CONTEXT_MODULE_STALE",
    "M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED",
    "M2_EVENT_KNOWLEDGE_GAP_CREATED",
    "M2_EVENT_MODEL_APPROVED",
    "M2_EVENT_MODEL_PROPOSED",
    "M2_EVENT_READINESS_ASSESSED",
    "M2_EVENT_SOURCE_REGISTERED",
    "M2_EVENT_SOURCE_STALE",
    "M2_INTELLIGENCE_COMMAND_TYPES",
    "READINESS_LEVEL_ORDER",
    "READINESS_PERMITTED_CAPABILITY",
    "REQUIRED_MODEL_SECTIONS",
    "STANDARD_CONTEXT_MODULE_KEYS",
    "TRUST_RANK",
    "WIS_EXPECTATIONS",
    "ContextItem",
    "ContextItemType",
    "ContextModule",
    "Contradiction",
    "ContradictionStatus",
    "DecisionOutcome",
    "DiscoveredSourceCandidate",
    "GapStatus",
    "IntentSeed",
    "KnowledgeGap",
    "ModelRevisionStatus",
    "ModelSectionState",
    "ModuleApprovalStatus",
    "ObservedSourcePath",
    "ReadinessLevel",
    "SectionCertainty",
    "SourceType",
    "StaleStatus",
    "TrustClass",
    "ValidationStatus",
    "WorkspaceDecision",
    "WorkspaceIntelligenceScenarioExpectation",
    "WorkspaceModelRevision",
    "WorkspaceReadinessAssessment",
    "WorkspaceSource",
    "assert_trust_promotion_allowed",
    "classify_observed_path",
    "invent_sources_from_observations",
    "observed_path_for_classification",
    "readiness_at_most",
    "readiness_level_index",
    "required_intelligence_scenario_ids",
    "section_certainty_map",
    "workspace_source_dedupe_key",
]
