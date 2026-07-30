"""M2-017 end-to-end workspace onboarding and refresh acceptance.

Proves the composed intelligence surface in one scenario:

onboard → discover/register → HUMAN trust + readiness decisions → activate →
refresh observations → query intelligence snapshot.

Does not cover Buzz (M2-009), M3 mission compilation, or conversation context
(M2-018).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from holodeck_governance.application.workspace_intelligence import (
    WorkspaceIntelligenceApplicationService,
)
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.assignments import RoleAssignment
from holodeck_governance.domain.authority.roles import RoleProfile
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    ContextModule,
    DecisionOutcome,
    GapStatus,
    IntentSeed,
    KnowledgeGap,
    ModelRevisionStatus,
    ModelSectionState,
    ModuleApprovalStatus,
    ObservedSourcePath,
    ReadinessLevel,
    REQUIRED_MODEL_SECTIONS,
    SectionCertainty,
    SourceRefreshObservation,
    SourceType,
    StaleStatus,
    TrustClass,
    TrustPromotion,
    WorkspaceCurationProposal,
    WorkspaceDecision,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.intelligence import (
    SqliteWorkspaceIntelligenceRepository,
)
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 18, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 29, 18, 30, tzinfo=UTC)
AFTER = datetime(2026, 7, 29, 19, 0, tzinfo=UTC)


def _grant_curate(conn: sqlite3.Connection, ids: FixtureIds, *, actor_id: str) -> None:
    auth = SqliteAuthorityRepository(conn)
    revisions = SqliteRevisionRepository(conn)
    role_object_id = generate_uuidv7()
    revisions.register_object(
        GovernanceObject(
            object_id=role_object_id,
            tenant_id=ids.tenant_alpha,
            object_type="RoleProfile",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_role_profile(
        RoleProfile(
            role_profile_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            role_object_id=role_object_id,
            revision=1,
            name="intelligence-curator",
            permissions=(INTELLIGENCE_CURATE_PERMISSION,),
            jurisdiction={"tenant": ids.tenant_alpha},
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_assignment(
        RoleAssignment(
            assignment_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            actor_id=actor_id,
            role_object_id=role_object_id,
            role_revision=1,
            workspace_object_id=None,
            jurisdiction_key="tenant",
            jurisdiction_value=ids.tenant_alpha,
            effective_from=NOW - timedelta(hours=1),
            created_at=NOW,
            created_by_actor_id=ids.system_service,
            effective_until=NOW + timedelta(days=30),
        )
    )


def _world() -> tuple[
    sqlite3.Connection, WorkspaceIntelligenceApplicationService, FixtureIds
]:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_governance(conn)
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    auth = SqliteAuthorityRepository(conn)
    for actor_id, name, kind in (
        (ids.human_owner, "Owner", ActorKind.HUMAN),
        (ids.system_service, "System", ActorKind.SERVICE),
    ):
        auth.save_actor(
            Actor(
                actor_id=actor_id,
                tenant_id=ids.tenant_alpha,
                kind=kind,
                display_name=name,
                created_at=FIXED_CLOCK,
                created_by_actor_id=ids.system_service,
            )
        )
    revisions = SqliteRevisionRepository(conn)
    revisions.register_object(
        GovernanceObject(
            object_id=ids.workspace_alpha_1,
            tenant_id=ids.tenant_alpha,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    _grant_curate(conn, ids, actor_id=ids.human_owner)
    _grant_curate(conn, ids, actor_id=ids.system_service)
    service = WorkspaceIntelligenceApplicationService(
        repository=SqliteWorkspaceIntelligenceRepository(conn)
    )
    return conn, service, ids


def _intent() -> IntentSeed:
    return IntentSeed(
        purpose_text="Governed local coordination",
        primary_users_text="Owners and delegated agents",
        important_risks_text="Silent instruction authority",
        non_goals_text="Replacing coding harnesses",
        decisions_not_automatic_text="Acceptance and production deploy",
    )


def _model(ids: FixtureIds) -> WorkspaceModelRevision:
    return WorkspaceModelRevision(
        model_revision_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        revision=1,
        status=ModelRevisionStatus.PROPOSED,
        intent_seed=_intent(),
        sections=tuple(
            ModelSectionState(section_key=key, certainty=SectionCertainty.PROPOSED)
            for key in REQUIRED_MODEL_SECTIONS
        ),
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        confidence_summary="onboarding candidate",
    )


def _source(ids: FixtureIds, *, locator: str = "repo://POLICY.md") -> WorkspaceSource:
    return WorkspaceSource(
        source_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        source_type=SourceType.DOCUMENT,
        locator=locator,
        observed_revision="rev-a",
        trust_class=TrustClass.ORDINARY_REFERENCE,
        owner_actor_id=ids.human_owner,
        sensitivity="public",
        refresh_policy="on_revision_change",
        observed_at=NOW,
        stale_status=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        module_tags=("security-and-authority",),
        current_observation_id=generate_uuidv7(),
    )


def _module(
    ids: FixtureIds,
    *,
    source_ids: tuple[str, ...],
    observation_ids: tuple[str, ...],
) -> ContextModule:
    return ContextModule(
        module_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        module_key="security-and-authority",
        purpose_text="Authority and policy context",
        applicability_text="all supervised work",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        revision=1,
        source_ids=source_ids,
        observation_ids=observation_ids,
    )


def test_m2_017_onboard_discover_activate_refresh_query_acceptance() -> None:
    conn, service, ids = _world()
    model = _model(ids)
    source = _source(ids)
    module = _module(
        ids,
        source_ids=(source.source_id,),
        observation_ids=(source.current_observation_id,),
    )
    gap = KnowledgeGap(
        gap_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        question="What is the approved authority boundary?",
        affected_sections=("architecture_and_system_map",),
        impact_text="Cannot claim governed readiness",
        risk_if_unresolved_text="Incorrect autonomous action",
        status=GapStatus.OPEN,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
    )
    readiness = WorkspaceReadinessAssessment(
        assessment_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        model_revision_id=model.model_revision_id,
        level=ReadinessLevel.DISCOVERED,
        dimensions_checked=("identity", "sources"),
        open_gap_ids=(gap.gap_id,),
        policy_basis="m2.onboarding.v1",
        evaluator_summary="proposed model with open gap",
        assessed_at=NOW,
        assessed_by_actor_id=ids.human_owner,
    )

    onboarded = service.onboard(
        model=model,
        sources=(source,),
        modules=(module,),
        gaps=(gap,),
        readiness=readiness,
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert onboarded.model_revision.status is ModelRevisionStatus.PROPOSED
    assert onboarded.readiness.level is ReadinessLevel.DISCOVERED
    assert len(onboarded.gaps) == 1

    discovered = service.discover_and_register_sources(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        observations=(
            ObservedSourcePath(
                locator="docs/architecture.md", observed_revision="rev-docs-1"
            ),
        ),
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert discovered.registered_count == 1
    discovered_source_id = discovered.registered_source_ids[0]
    # Discovery never invents instruction authority.
    discovered_source = service.get_source(discovered_source_id)
    assert discovered_source is not None
    assert discovered_source.trust_class is not TrustClass.INSTRUCTION_AUTHORITY
    assert discovered_source.instruction_authority is False

    # Resolve the open gap before governed activation (open gaps cap at DISCOVERED).
    # Gaps are insert-immutable; resolution is an explicit store update that
    # requires an in-tenant external reference id.
    resolution_reference_id = generate_uuidv7()
    conn.execute(
        """
        INSERT INTO gov_external_references(
            reference_id, tenant_id, provider, object_type, external_object_id,
            locator, observed_at, created_at, created_by_actor_id, schema_version
        ) VALUES (?, ?, 'memory', 'decision', 'gap-resolution-1',
                  'memory://gap-resolution-1', ?, ?, ?, 'm1.external_reference.v1')
        """,
        (
            resolution_reference_id,
            ids.tenant_alpha,
            LATER.isoformat(),
            LATER.isoformat(),
            ids.human_owner,
        ),
    )
    conn.commit()
    resolved_gap = service.resolve_knowledge_gap(
        gap.gap_id,
        tenant_id=ids.tenant_alpha,
        resolution_reference_id=resolution_reference_id,
        actor_id=ids.human_owner,
        at=LATER,
    )
    assert resolved_gap.status is GapStatus.RESOLVED
    assert resolved_gap.resolution_reference_id == resolution_reference_id

    # Curate alone cannot self-declare operationally assured without evidence/decision.
    with pytest.raises(
        MalformedCommandError,
        match="readiness cannot exceed|readiness_decision_id is required",
    ):
        service.save_readiness_assessment(
            WorkspaceReadinessAssessment(
                assessment_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_alpha_1,
                model_revision_id=model.model_revision_id,
                level=ReadinessLevel.OPERATIONALLY_ASSURED,
                dimensions_checked=("identity",),
                open_gap_ids=(),
                policy_basis="m2.onboarding.v1",
                evaluator_summary="bypass attempt",
                assessed_at=LATER,
                assessed_by_actor_id=ids.system_service,
            )
        )

    trust_decision = WorkspaceDecision(
        decision_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        subject_revision_id=source.source_id,
        outcome=DecisionOutcome.APPROVED,
        rationale="Human approved instruction authority for POLICY.md",
        authorized_actor_id=ids.human_owner,
        decided_at=LATER,
    )
    service.save_workspace_decision(trust_decision)
    readiness_decision = WorkspaceDecision(
        decision_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        subject_revision_id=model.model_revision_id,
        outcome=DecisionOutcome.APPROVED,
        rationale="Human authorized governed readiness",
        authorized_actor_id=ids.human_owner,
        decided_at=LATER,
        authorized_readiness_level=ReadinessLevel.GOVERNED,
    )
    service.save_workspace_decision(readiness_decision)

    activated = service.activate_curation(
        WorkspaceCurationProposal(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            model_revision_id=model.model_revision_id,
            module_ids_to_approve=(module.module_id,),
            trust_promotions=(
                TrustPromotion(
                    source_id=source.source_id,
                    to_trust=TrustClass.INSTRUCTION_AUTHORITY,
                    decision_id=trust_decision.decision_id,
                ),
            ),
            claimed_readiness_level=ReadinessLevel.GOVERNED,
            dimensions_checked=("identity", "authority", "sources"),
            open_gap_ids=(),
            policy_basis="m2.curation.v1",
            evaluator_summary="human-curated governed workspace",
            actor_id=ids.human_owner,
            at=LATER,
            readiness_decision_id=readiness_decision.decision_id,
        )
    )
    assert activated.approved_model.status is ModelRevisionStatus.APPROVED
    assert activated.readiness.level is ReadinessLevel.GOVERNED
    promoted = service.get_source(source.source_id)
    assert promoted is not None
    assert promoted.trust_class is TrustClass.INSTRUCTION_AUTHORITY
    assert promoted.promotion_decision_id == trust_decision.decision_id
    assert (
        service.get_context_module(module.module_id).approval_status
        is ModuleApprovalStatus.APPROVED
    )

    prior_observations = service.list_source_observations(
        source.source_id, tenant_id=ids.tenant_alpha
    )
    assert len(prior_observations) == 1
    prior_observation_id = prior_observations[0].observation_id

    refreshed = service.refresh_sources(
        ids.workspace_alpha_1,
        tenant_id=ids.tenant_alpha,
        observations=(
            SourceRefreshObservation(
                source_id=source.source_id,
                new_observed_revision="rev-b",
                content_hash="hash-b",
            ),
        ),
        actor_id=ids.human_owner,
        at=AFTER,
    )
    assert refreshed.refreshed_source_ids == (source.source_id,)
    assert module.module_id in refreshed.staled_module_ids

    observations = service.list_source_observations(
        source.source_id, tenant_id=ids.tenant_alpha
    )
    assert len(observations) == 2
    assert observations[0].observation_id == prior_observation_id
    assert observations[0].observed_revision == "rev-a"
    assert observations[1].observed_revision == "rev-b"
    assert service.get_source_observation(prior_observation_id) is not None
    current = service.get_source(source.source_id)
    assert current is not None
    assert current.observed_revision == "rev-b"
    assert current.current_observation_id == observations[1].observation_id
    assert current.stale_status is StaleStatus.STALE
    assert service.get_context_module(module.module_id).freshness is StaleStatus.STALE

    snapshot = service.query_workspace_intelligence(
        ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
    )
    assert snapshot.model is not None
    assert snapshot.model.model_revision_id == model.model_revision_id
    assert snapshot.model.status is ModelRevisionStatus.APPROVED
    assert len(snapshot.sources) >= 2
    assert any(item.source_id == source.source_id for item in snapshot.sources)
    assert any(item.module_id == module.module_id for item in snapshot.modules)
    assert snapshot.open_gaps == ()
    assert snapshot.latest_readiness is not None
    assert snapshot.latest_readiness.level is ReadinessLevel.GOVERNED
    assert source.source_id in snapshot.stale_source_ids
    assert module.module_id in snapshot.stale_module_ids

    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Mission'"
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Run'"
        ).fetchone()[0]
        == 0
    )
