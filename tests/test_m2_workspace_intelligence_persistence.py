"""M2-013 workspace intelligence persistence and application operations."""

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
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    IdempotencyConflictError,
    MalformedCommandError,
    MissingAuthorityError,
    NotFoundGovernanceError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    M2_EVENT_CONTEXT_MODULE_STALE,
    M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED,
    M2_EVENT_KNOWLEDGE_GAP_CREATED,
    M2_EVENT_MODEL_APPROVED,
    M2_EVENT_MODEL_PROPOSED,
    M2_EVENT_READINESS_ASSESSED,
    M2_EVENT_SOURCE_REGISTERED,
    M2_EVENT_SOURCE_STALE,
    REQUIRED_MODEL_SECTIONS,
    ContextItem,
    ContextItemType,
    ContextModule,
    Contradiction,
    ContradictionStatus,
    DecisionOutcome,
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
    WorkspaceDecision,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.intelligence import (
    SqliteWorkspaceIntelligenceRepository,
)
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
)
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 14, 0, tzinfo=UTC)


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


def _service() -> tuple[
    sqlite3.Connection, WorkspaceIntelligenceApplicationService, FixtureIds, str
]:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_governance(conn)
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'beta', 'Beta', 'm1.tenant.v1', ?, ?, NULL, 'active', 0)
        """,
        (ids.tenant_beta, NOW.isoformat(), ids.system_service),
    )
    auth = SqliteAuthorityRepository(conn)
    unauthorized = generate_uuidv7()
    for actor_id, tenant_id, name, kind in (
        (ids.human_owner, ids.tenant_alpha, "Owner", ActorKind.HUMAN),
        (ids.system_service, ids.tenant_alpha, "System", ActorKind.SERVICE),
        (unauthorized, ids.tenant_alpha, "NoAuth", ActorKind.HUMAN),
        (ids.human_reviewer, ids.tenant_beta, "Beta", ActorKind.HUMAN),
    ):
        auth.save_actor(
            Actor(
                actor_id=actor_id,
                tenant_id=tenant_id,
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
    revisions.register_object(
        GovernanceObject(
            object_id=ids.workspace_beta_1,
            tenant_id=ids.tenant_beta,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    _grant_curate(conn, ids, actor_id=ids.human_owner)
    service = WorkspaceIntelligenceApplicationService(
        repository=SqliteWorkspaceIntelligenceRepository(conn)
    )
    return conn, service, ids, unauthorized


def _intent() -> IntentSeed:
    return IntentSeed(
        purpose_text="Governed local coordination",
        primary_users_text="Owners and delegated agents",
        important_risks_text="Silent instruction authority",
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


def _model(ids: FixtureIds, *, revision: int = 1) -> WorkspaceModelRevision:
    return WorkspaceModelRevision(
        model_revision_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        revision=revision,
        status=ModelRevisionStatus.PROPOSED,
        intent_seed=_intent(),
        sections=_sections(),
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        confidence_summary="mostly unknown at onboarding",
    )


def _source(
    ids: FixtureIds,
    *,
    locator: str = "repo://README.md",
    trust: TrustClass = TrustClass.UNTRUSTED_REFERENCE,
    tags: tuple[str, ...] = ("architecture",),
) -> WorkspaceSource:
    return WorkspaceSource(
        source_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        source_type=SourceType.REPOSITORY_FILE,
        locator=locator,
        observed_revision="abc123",
        trust_class=trust,
        owner_actor_id=ids.human_owner,
        sensitivity="public",
        refresh_policy="on_revision_change",
        observed_at=NOW,
        stale_status=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        module_tags=tags,
        current_observation_id=generate_uuidv7(),
    )


def _module(
    ids: FixtureIds,
    *,
    key: str = "architecture",
    source_ids: tuple[str, ...] = (),
    observation_ids: tuple[str, ...] = (),
) -> ContextModule:
    return ContextModule(
        module_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        module_key=key,
        purpose_text=f"{key} context",
        applicability_text="all supervised work",
        approval_status=ModuleApprovalStatus.PROPOSED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        source_ids=source_ids,
        observation_ids=observation_ids,
    )


def _gap(ids: FixtureIds) -> KnowledgeGap:
    return KnowledgeGap(
        gap_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        question="What is the approved deployment topology?",
        affected_sections=("architecture_and_system_map",),
        impact_text="Cannot claim governed readiness",
        risk_if_unresolved_text="Incorrect autonomous action",
        status=GapStatus.OPEN,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
    )


def _readiness(
    ids: FixtureIds,
    *,
    model_id: str,
    level: ReadinessLevel = ReadinessLevel.DISCOVERED,
    open_gap_ids: tuple[str, ...] = (),
) -> WorkspaceReadinessAssessment:
    return WorkspaceReadinessAssessment(
        assessment_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        model_revision_id=model_id,
        level=level,
        dimensions_checked=("identity", "sources"),
        open_gap_ids=open_gap_ids,
        policy_basis="m2.onboarding.v1",
        evaluator_summary="discovered with open gaps",
        assessed_at=NOW,
        assessed_by_actor_id=ids.human_owner,
    )


def test_migrate_v19_creates_intelligence_tables() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    assert governance_schema_version(conn) == 23
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for name in (
        "gov_workspace_model_revisions",
        "gov_workspace_sources",
        "gov_context_items",
        "gov_context_modules",
        "gov_knowledge_gaps",
        "gov_contradictions",
        "gov_workspace_decisions",
        "gov_workspace_readiness_assessments",
    ):
        assert name in tables
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(gov_workspace_sources)").fetchall()
    }
    assert "promotion_decision_id" in columns


def test_onboard_persists_intelligence_without_mission_or_run() -> None:
    conn, service, ids, _ = _service()
    model = _model(ids)
    source = _source(ids)
    module = _module(ids, source_ids=(source.source_id,), observation_ids=(source.current_observation_id,))
    gap = _gap(ids)
    readiness = _readiness(ids, model_id=model.model_revision_id, open_gap_ids=(gap.gap_id,))

    result = service.onboard(
        model=model,
        sources=(source,),
        modules=(module,),
        gaps=(gap,),
        readiness=readiness,
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert result.model_revision.model_revision_id == model.model_revision_id
    assert service.get_model_revision(model.model_revision_id) is not None
    assert service.get_source(source.source_id) is not None
    assert service.get_context_module(module.module_id) is not None
    assert service.get_knowledge_gap(gap.gap_id) is not None
    assert service.get_latest_readiness(
        ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
    ) is not None
    events = {
        str(row[0])
        for row in conn.execute("SELECT event_type FROM gov_domain_events").fetchall()
    }
    assert M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED in events
    assert M2_EVENT_MODEL_PROPOSED in events
    assert M2_EVENT_SOURCE_REGISTERED in events
    assert M2_EVENT_KNOWLEDGE_GAP_CREATED in events
    assert M2_EVENT_READINESS_ASSESSED in events
    assert conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Mission'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Run'"
    ).fetchone()[0] == 0


def test_untrusted_source_cannot_silently_become_instruction_authority() -> None:
    _conn, service, ids, _ = _service()
    source = _source(ids)
    service.register_source(source)
    with pytest.raises(MalformedCommandError, match="decision_id"):
        service.update_source_trust(
            source.source_id,
            tenant_id=ids.tenant_alpha,
            to_trust=TrustClass.INSTRUCTION_AUTHORITY,
            actor_id=ids.human_owner,
            at=NOW,
        )
    decision = WorkspaceDecision(
        decision_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        subject_revision_id=source.source_id,
        outcome=DecisionOutcome.APPROVED,
        rationale="Human approved instruction authority",
        authorized_actor_id=ids.human_owner,
        decided_at=NOW,
    )
    service.save_workspace_decision(decision)
    promoted = service.update_source_trust(
        source.source_id,
        tenant_id=ids.tenant_alpha,
        to_trust=TrustClass.INSTRUCTION_AUTHORITY,
        actor_id=ids.human_owner,
        at=NOW,
        promotion_decision_id=decision.decision_id,
    )
    assert promoted.trust_class is TrustClass.INSTRUCTION_AUTHORITY
    assert promoted.instruction_authority is True
    assert promoted.promotion_decision_id == decision.decision_id


def test_generated_summary_requires_provenance_and_cannot_be_instruction() -> None:
    conn, service, ids, _ = _service()
    ref = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="git",
        object_type="repository_file",
        external_object_id="README.md",
        locator="repo://README.md",
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    from holodeck_governance.storage.sqlite.graph_seed import persist_external_reference

    persist_external_reference(conn, ref)
    item = ContextItem(
        item_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        item_type=ContextItemType.GENERATED_SUMMARY,
        statement="Repo appears to be a Python package",
        trust_class=TrustClass.GENERATED_INTERPRETATION,
        validation_status=ValidationStatus.UNVERIFIED,
        freshness=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        source_reference_ids=(ref.reference_id,),
        confidence=0.55,
    )
    service.save_context_item(item)
    stored = service.get_context_item(item.item_id)
    assert stored is not None
    assert stored.confidence == 0.55
    assert stored.source_reference_ids == (ref.reference_id,)
    with pytest.raises(MalformedCommandError):
        ContextItem(
            item_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            item_type=ContextItemType.GENERATED_SUMMARY,
            statement="bad",
            trust_class=TrustClass.INSTRUCTION_AUTHORITY,
            validation_status=ValidationStatus.UNVERIFIED,
            freshness=StaleStatus.FRESH,
            created_at=NOW,
            created_by_actor_id=ids.human_owner,
            source_reference_ids=(ref.reference_id,),
            confidence=0.5,
        )


def test_context_item_rejects_unknown_source_reference() -> None:
    _conn, service, ids, _ = _service()
    with pytest.raises(NotFoundGovernanceError, match="unknown external reference"):
        service.save_context_item(
            ContextItem(
                item_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_alpha_1,
                item_type=ContextItemType.SOURCE_FACT,
                statement="missing ref",
                trust_class=TrustClass.ORDINARY_REFERENCE,
                validation_status=ValidationStatus.UNVERIFIED,
                freshness=StaleStatus.FRESH,
                created_at=NOW,
                created_by_actor_id=ids.human_owner,
                source_reference_ids=(generate_uuidv7(),),
            )
        )


def test_context_module_rejects_unknown_item_and_source_ids() -> None:
    _conn, service, ids, _ = _service()
    with pytest.raises(NotFoundGovernanceError, match="unknown context item"):
        service.save_context_module(
            ContextModule(
                module_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_alpha_1,
                module_key="architecture",
                purpose_text="arch",
                applicability_text="all",
                approval_status=ModuleApprovalStatus.PROPOSED,
                freshness=StaleStatus.FRESH,
                created_at=NOW,
                created_by_actor_id=ids.human_owner,
                item_ids=(generate_uuidv7(),),
            )
        )
    with pytest.raises(NotFoundGovernanceError, match="unknown source"):
        service.save_context_module(
            ContextModule(
                module_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_alpha_1,
                module_key="architecture",
                purpose_text="arch",
                applicability_text="all",
                approval_status=ModuleApprovalStatus.PROPOSED,
                freshness=StaleStatus.FRESH,
                created_at=NOW,
                created_by_actor_id=ids.human_owner,
                source_ids=(generate_uuidv7(),),
                observation_ids=(generate_uuidv7(),),
            )
        )


def test_mark_source_stale_only_affects_dependent_modules() -> None:
    conn, service, ids, _ = _service()
    source = _source(ids)
    dependent = _module(ids, key="architecture", source_ids=(source.source_id,), observation_ids=(source.current_observation_id,))
    unrelated = _module(ids, key="domain-language")
    service.register_source(source)
    service.save_context_module(dependent)
    service.save_context_module(unrelated)

    service.mark_source_stale(
        source.source_id,
        tenant_id=ids.tenant_alpha,
        dependent_module_ids=(dependent.module_id,),
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert service.get_source(source.source_id).stale_status is StaleStatus.STALE
    assert service.get_context_module(dependent.module_id).freshness is StaleStatus.STALE
    assert service.get_context_module(unrelated.module_id).freshness is StaleStatus.FRESH
    events = [
        str(row[0])
        for row in conn.execute("SELECT event_type FROM gov_domain_events").fetchall()
    ]
    assert M2_EVENT_SOURCE_STALE in events
    assert events.count(M2_EVENT_CONTEXT_MODULE_STALE) == 1


def test_contradiction_remains_open_until_resolved() -> None:
    _conn, service, ids, _ = _service()
    contra = Contradiction(
        contradiction_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        claim_reference_ids=(generate_uuidv7(), generate_uuidv7()),
        description="Two docs disagree on default branch policy",
        impact_text="Ambiguous release gate",
        status=ContradictionStatus.OPEN,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
    )
    service.save_contradiction(contra)
    assert service.get_contradiction(contra.contradiction_id).status is ContradictionStatus.OPEN
    resolution = generate_uuidv7()
    # resolution_reference_id must exist in gov_external_references for FK/trigger.
    conn = _conn
    conn.execute(
        """
        INSERT INTO gov_external_references(
            reference_id, tenant_id, provider, object_type, external_object_id,
            locator, observed_at, created_at, created_by_actor_id, schema_version
        ) VALUES (?, ?, 'memory', 'decision', 'res-1', 'memory://res-1', ?, ?, ?, 'm1.external_reference.v1')
        """,
        (resolution, ids.tenant_alpha, NOW.isoformat(), NOW.isoformat(), ids.system_service),
    )
    conn.commit()
    resolved = service.resolve_contradiction(
        contra.contradiction_id,
        tenant_id=ids.tenant_alpha,
        resolution_reference_id=resolution,
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert resolved.status is ContradictionStatus.RESOLVED
    assert resolved.resolution_reference_id == resolution


def test_readiness_governed_with_open_gaps_rejected_and_prior_revisions_queryable() -> None:
    _conn, service, ids, _ = _service()
    first = _model(ids, revision=1)
    service.save_model_revision(first)
    approved = service.approve_model_revision(
        first.model_revision_id,
        tenant_id=ids.tenant_alpha,
        approved_by_actor_id=ids.human_owner,
        approved_at=NOW,
    )
    assert approved.status is ModelRevisionStatus.APPROVED
    assert M2_EVENT_MODEL_APPROVED  # import retained for catalog presence

    second = WorkspaceModelRevision(
        model_revision_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        revision=2,
        status=ModelRevisionStatus.PROPOSED,
        intent_seed=_intent(),
        sections=_sections(SectionCertainty.PROPOSED),
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        based_on_revision_id=first.model_revision_id,
    )
    service.save_model_revision(second)
    service.approve_model_revision(
        second.model_revision_id,
        tenant_id=ids.tenant_alpha,
        approved_by_actor_id=ids.human_owner,
        approved_at=NOW,
    )
    revisions = service.list_model_revisions(
        ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
    )
    assert len(revisions) == 2
    by_id = {item.model_revision_id: item for item in revisions}
    assert by_id[first.model_revision_id].status is ModelRevisionStatus.SUPERSEDED
    assert by_id[second.model_revision_id].status is ModelRevisionStatus.APPROVED

    with pytest.raises(MalformedCommandError):
        WorkspaceReadinessAssessment(
            assessment_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            model_revision_id=second.model_revision_id,
            level=ReadinessLevel.GOVERNED,
            dimensions_checked=("authority",),
            open_gap_ids=(generate_uuidv7(),),
            policy_basis="m2",
            evaluator_summary="should fail",
            assessed_at=NOW,
            assessed_by_actor_id=ids.human_owner,
        )


def test_missing_curate_permission_and_cross_tenant_denied() -> None:
    _conn, service, ids, unauthorized = _service()
    model = _model(ids)
    with pytest.raises(MissingAuthorityError):
        service.save_model_revision(
            WorkspaceModelRevision(
                model_revision_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_alpha_1,
                revision=1,
                status=ModelRevisionStatus.PROPOSED,
                intent_seed=_intent(),
                sections=_sections(),
                created_at=NOW,
                created_by_actor_id=unauthorized,
            )
        )
    with pytest.raises(CrossTenantAccessError):
        service.save_model_revision(
            WorkspaceModelRevision(
                model_revision_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_beta_1,
                revision=1,
                status=ModelRevisionStatus.PROPOSED,
                intent_seed=_intent(),
                sections=_sections(),
                created_at=NOW,
                created_by_actor_id=ids.human_owner,
            )
        )


def test_duplicate_source_natural_key_rejected() -> None:
    _conn, service, ids, _ = _service()
    first = _source(ids, locator="repo://dup.md")
    service.register_source(first)
    with pytest.raises(IdempotencyConflictError):
        service.register_source(_source(ids, locator="repo://dup.md"))


def test_observation_insert_rejects_cross_tenant_workspace_coupling() -> None:
    conn, service, ids, _ = _service()
    source = _source(ids)
    service.register_source(source)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO gov_workspace_source_observations(
                observation_id, source_id, tenant_id, workspace_object_id,
                observed_revision, content_hash, observed_at, created_at,
                created_by_actor_id, schema_version
            ) VALUES (?, ?, ?, ?, 'rev', NULL, ?, ?, ?, 'm2.workspace_source_observation.v1')
            """,
            (
                generate_uuidv7(),
                source.source_id,
                ids.tenant_beta,
                ids.workspace_beta_1,
                NOW.isoformat(),
                NOW.isoformat(),
                ids.human_reviewer,
            ),
        )
        conn.commit()


def test_module_rejects_nonexistent_and_wrong_source_observation_ids() -> None:
    _conn, service, ids, _ = _service()
    source = _source(ids)
    other = _source(ids, locator="repo://OTHER.md")
    service.register_source(source)
    service.register_source(other)
    with pytest.raises(NotFoundGovernanceError, match="unknown source observation"):
        service.save_context_module(
            _module(
                ids,
                source_ids=(source.source_id,),
                observation_ids=(generate_uuidv7(),),
            )
        )
    with pytest.raises(
        MalformedCommandError, match="observation_id does not belong to module source_ids"
    ):
        service.save_context_module(
            _module(
                ids,
                source_ids=(source.source_id,),
                observation_ids=(other.current_observation_id,),
            )
        )
