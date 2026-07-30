"""M2-012 workspace intelligence contract suite."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.workspace.intelligence import (
    M2_INTELLIGENCE_COMMAND_TYPES,
    REQUIRED_MODEL_SECTIONS,
    STANDARD_CONTEXT_MODULE_KEYS,
    WIS_EXPECTATIONS,
    ContextItem,
    ContextItemType,
    ContextModule,
    Contradiction,
    ContradictionStatus,
    GapStatus,
    IntentSeed,
    KnowledgeGap,
    ModelRevisionStatus,
    ModelSectionState,
    ModuleApprovalStatus,
    ReadinessLevel,
    SectionCertainty,
    SourceType,
    StaleStatus,
    TrustClass,
    ValidationStatus,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
    assert_trust_promotion_allowed,
    readiness_at_most,
    required_intelligence_scenario_ids,
    trust_promotion_requires_human_decision,
    workspace_source_dedupe_key,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "plans" / "2026-07-27-workspace-model-and-intelligence-design.md"
INTEL_DOMAIN = (
    ROOT / "src" / "holodeck_governance" / "domain" / "workspace" / "intelligence"
)

TENANT = "00000000-0000-7000-8000-0000000000a1"
ACTOR = "00000000-0000-7000-8000-0000000000a2"
WORKSPACE = "00000000-0000-7000-8000-0000000000b1"
MODEL = "00000000-0000-7000-8000-0000000000b2"
SOURCE = "00000000-0000-7000-8000-0000000000b3"
ITEM = "00000000-0000-7000-8000-0000000000b4"
MODULE = "00000000-0000-7000-8000-0000000000b5"
OBSERVATION = "00000000-0000-7000-8000-0000000000b6"
GAP = "00000000-0000-7000-8000-0000000000b6"
CONTRA = "00000000-0000-7000-8000-0000000000b7"
ASSESS = "00000000-0000-7000-8000-0000000000b8"
REF_A = "00000000-0000-7000-8000-0000000000c1"
REF_B = "00000000-0000-7000-8000-0000000000c2"
NOW = datetime(2026, 7, 29, 13, 0, tzinfo=UTC)


def _intent() -> IntentSeed:
    return IntentSeed(
        purpose_text="Governed local coordination for agent work",
        primary_users_text="Human owners and delegated agents",
        important_risks_text="Silent instruction authority from repo text",
        non_goals_text="Replacing coding harnesses",
        decisions_not_automatic_text="Acceptance and production deploy",
    )


def _sections(
    certainty: SectionCertainty = SectionCertainty.UNKNOWN,
) -> tuple[ModelSectionState, ...]:
    return tuple(
        ModelSectionState(section_key=key, certainty=certainty)
        for key in REQUIRED_MODEL_SECTIONS
    )


def test_design_doc_names_required_intelligence_entities() -> None:
    text = DESIGN.read_text(encoding="utf-8")
    for needle in (
        "WorkspaceModelRevision",
        "WorkspaceSource",
        "ContextModule",
        "KnowledgeGap",
        "WorkspaceReadinessAssessment",
        "instruction_authority",
    ):
        assert needle in text


def test_wis_catalog_is_complete() -> None:
    assert required_intelligence_scenario_ids() == tuple(
        f"WIS-{i:03d}" for i in range(1, 7)
    )
    assert set(WIS_EXPECTATIONS) == set(required_intelligence_scenario_ids())
    for expectation in WIS_EXPECTATIONS.values():
        for command in expectation.m1_command_types:
            assert command in M2_INTELLIGENCE_COMMAND_TYPES


def test_model_revision_requires_all_sections_and_intent() -> None:
    revision = WorkspaceModelRevision(
        model_revision_id=MODEL,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        revision=1,
        status=ModelRevisionStatus.PROPOSED,
        intent_seed=_intent(),
        sections=_sections(),
        created_at=NOW,
        created_by_actor_id=ACTOR,
    )
    assert len(revision.sections) == 7
    with pytest.raises(MalformedCommandError):
        WorkspaceModelRevision(
            model_revision_id=MODEL,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            revision=1,
            status=ModelRevisionStatus.PROPOSED,
            intent_seed=_intent(),
            sections=_sections()[:3],
            created_at=NOW,
            created_by_actor_id=ACTOR,
        )


def test_generated_source_cannot_be_instruction_authority() -> None:
    with pytest.raises(MalformedCommandError):
        WorkspaceSource(
            source_id=SOURCE,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            source_type=SourceType.GENERATED_INTERPRETATION,
            locator="memory://summaries/1",
            observed_revision="sum-1",
            trust_class=TrustClass.INSTRUCTION_AUTHORITY,
            owner_actor_id=ACTOR,
            sensitivity="internal",
            refresh_policy="manual",
            observed_at=NOW,
            stale_status=StaleStatus.FRESH,
            created_at=NOW,
            created_by_actor_id=ACTOR,
            instruction_authority=True,
        )


def test_trust_promotion_requires_human_decision_id() -> None:
    with pytest.raises(MalformedCommandError):
        assert_trust_promotion_allowed(
            from_trust=TrustClass.UNTRUSTED_REFERENCE,
            to_trust=TrustClass.INSTRUCTION_AUTHORITY,
            decision_id=None,
        )
    assert_trust_promotion_allowed(
        from_trust=TrustClass.UNTRUSTED_REFERENCE,
        to_trust=TrustClass.INSTRUCTION_AUTHORITY,
        decision_id=SOURCE,
    )
    assert not trust_promotion_requires_human_decision(
        TrustClass.ORDINARY_REFERENCE,
        TrustClass.TRUSTED_OBSERVATION,
    )
    assert trust_promotion_requires_human_decision(
        TrustClass.UNTRUSTED_REFERENCE,
        TrustClass.AUTHORITATIVE_REFERENCE,
    )


def test_generated_summary_requires_confidence_and_sources() -> None:
    with pytest.raises(MalformedCommandError):
        ContextItem(
            item_id=ITEM,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            item_type=ContextItemType.GENERATED_SUMMARY,
            statement="Architecture looks layered",
            trust_class=TrustClass.GENERATED_INTERPRETATION,
            validation_status=ValidationStatus.UNVERIFIED,
            freshness=StaleStatus.FRESH,
            created_at=NOW,
            created_by_actor_id=ACTOR,
        )
    item = ContextItem(
        item_id=ITEM,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        item_type=ContextItemType.GENERATED_SUMMARY,
        statement="Architecture looks layered",
        trust_class=TrustClass.GENERATED_INTERPRETATION,
        validation_status=ValidationStatus.UNVERIFIED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ACTOR,
        source_reference_ids=(REF_A,),
        confidence=0.55,
    )
    assert item.confidence == 0.55


def test_context_module_uses_standard_keys() -> None:
    module = ContextModule(
        module_id=MODULE,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        module_key="architecture",
        purpose_text="System map",
        applicability_text="All implementation tasks",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ACTOR,
        source_ids=(SOURCE,),
        observation_ids=(OBSERVATION,),
        item_ids=(ITEM,),
    )
    assert module.module_key in STANDARD_CONTEXT_MODULE_KEYS
    with pytest.raises(MalformedCommandError):
        ContextModule(
            module_id=MODULE,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            module_key="mystery-module",
            purpose_text="x",
            applicability_text="y",
            approval_status=ModuleApprovalStatus.PROPOSED,
            freshness=StaleStatus.FRESH,
            created_at=NOW,
            created_by_actor_id=ACTOR,
        )


def test_contradiction_requires_two_claims_and_stays_open_without_resolution() -> None:
    open_contra = Contradiction(
        contradiction_id=CONTRA,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        claim_reference_ids=(REF_A, REF_B),
        description="Docs disagree on deploy target",
        impact_text="Blocks governed readiness",
        status=ContradictionStatus.OPEN,
        created_at=NOW,
        created_by_actor_id=ACTOR,
    )
    assert open_contra.resolution_reference_id is None
    with pytest.raises(MalformedCommandError):
        Contradiction(
            contradiction_id=CONTRA,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            claim_reference_ids=(REF_A,),
            description="only one claim",
            impact_text="x",
            status=ContradictionStatus.OPEN,
            created_at=NOW,
            created_by_actor_id=ACTOR,
        )


def test_readiness_cannot_exceed_evidence_or_keep_gaps_when_governed() -> None:
    readiness_at_most(
        claimed=ReadinessLevel.DISCOVERED,
        evidenced_maximum=ReadinessLevel.CONTEXTUALIZED,
    )
    with pytest.raises(MalformedCommandError):
        readiness_at_most(
            claimed=ReadinessLevel.GOVERNED,
            evidenced_maximum=ReadinessLevel.DISCOVERED,
        )
    with pytest.raises(MalformedCommandError):
        WorkspaceReadinessAssessment(
            assessment_id=ASSESS,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            model_revision_id=MODEL,
            level=ReadinessLevel.GOVERNED,
            dimensions_checked=("authority", "invariants"),
            open_gap_ids=(GAP,),
            policy_basis="m2.readiness.v1",
            evaluator_summary="gaps remain",
            assessed_at=NOW,
            assessed_by_actor_id=ACTOR,
        )
    assessment = WorkspaceReadinessAssessment(
        assessment_id=ASSESS,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        model_revision_id=MODEL,
        level=ReadinessLevel.CONTEXTUALIZED,
        dimensions_checked=("purpose", "users", "capabilities"),
        open_gap_ids=(GAP,),
        policy_basis="m2.readiness.v1",
        evaluator_summary="contextualized with open gaps",
        assessed_at=NOW,
        assessed_by_actor_id=ACTOR,
    )
    assert assessment.permitted_capability == "planning_and_supervised_proposals"


def test_knowledge_gap_and_source_dedupe_shape() -> None:
    gap = KnowledgeGap(
        gap_id=GAP,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        question="What is the rollback policy?",
        affected_sections=("engineering_principles_and_constraints",),
        impact_text="Blocks verifiable readiness",
        risk_if_unresolved_text="Unsafe autonomous deploy",
        status=GapStatus.OPEN,
        created_at=NOW,
        created_by_actor_id=ACTOR,
    )
    assert gap.status is GapStatus.OPEN
    source = WorkspaceSource(
        source_id=SOURCE,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        source_type=SourceType.REPOSITORY_FILE,
        locator="git://repo#README.md",
        observed_revision="abc123",
        trust_class=TrustClass.ORDINARY_REFERENCE,
        owner_actor_id=ACTOR,
        sensitivity="public",
        refresh_policy="on_commit",
        observed_at=NOW,
        stale_status=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ACTOR,
        module_tags=("architecture",),
    )
    assert workspace_source_dedupe_key(source) == (
        TENANT,
        WORKSPACE,
        "git://repo#README.md",
    )


def test_intelligence_package_forbids_provider_and_storage_imports() -> None:
    forbidden_prefixes = (
        "sqlite3",
        "http",
        "urllib",
        "mcp",
        "buzz",
        "holodeck_governance.application",
        "holodeck_governance.storage",
        "holodeck_governance.adapters",
        "holodeck_control_plane",
    )
    violations: list[str] = []
    for path in INTEL_DOMAIN.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in forbidden_prefixes
                ):
                    violations.append(f"{path.name} imports {name}")
    assert violations == []
