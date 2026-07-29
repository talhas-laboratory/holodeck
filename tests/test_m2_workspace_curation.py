"""M2-015 workspace curation, approval, activation, and readiness reassessment."""

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
    MalformedCommandError,
    MissingAuthorityError,
    NotFoundGovernanceError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    M2_EVENT_MODEL_APPROVED,
    M2_EVENT_READINESS_ASSESSED,
    REQUIRED_MODEL_SECTIONS,
    IntentSeed,
    ModelRevisionStatus,
    ModelSectionState,
    ModuleApprovalStatus,
    ObservedSourcePath,
    ReadinessLevel,
    SectionCertainty,
    SourceType,
    StaleStatus,
    TrustClass,
    TrustPromotion,
    WorkspaceCurationProposal,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
    validate_curation_proposal,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.intelligence import (
    SqliteWorkspaceIntelligenceRepository,
)
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 17, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 29, 17, 30, tzinfo=UTC)


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
    certainty: SectionCertainty = SectionCertainty.PROPOSED,
) -> tuple[ModelSectionState, ...]:
    return tuple(
        ModelSectionState(section_key=key, certainty=certainty)
        for key in REQUIRED_MODEL_SECTIONS
    )


def _model(
    ids: FixtureIds, *, revision: int = 1, model_id: str | None = None
) -> WorkspaceModelRevision:
    return WorkspaceModelRevision(
        model_revision_id=model_id or generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        revision=revision,
        status=ModelRevisionStatus.PROPOSED,
        intent_seed=_intent(),
        sections=_sections(),
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        confidence_summary="curation candidate",
    )


def _source(
    ids: FixtureIds,
    *,
    locator: str = "repo://POLICY.md",
    trust: TrustClass = TrustClass.ORDINARY_REFERENCE,
) -> WorkspaceSource:
    return WorkspaceSource(
        source_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        source_type=SourceType.DOCUMENT,
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
        module_tags=("architecture",),
    )


def _module(
    ids: FixtureIds,
    *,
    key: str = "architecture",
    revision: int = 1,
    source_ids: tuple[str, ...] = (),
):
    from holodeck_governance.domain.workspace.intelligence import ContextModule

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
        revision=revision,
        source_ids=source_ids,
    )


def _readiness(ids: FixtureIds, *, model_id: str) -> WorkspaceReadinessAssessment:
    return WorkspaceReadinessAssessment(
        assessment_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        model_revision_id=model_id,
        level=ReadinessLevel.DISCOVERED,
        dimensions_checked=("identity", "sources"),
        open_gap_ids=(),
        policy_basis="m2.onboarding.v1",
        evaluator_summary="discovered at onboard",
        assessed_at=NOW,
        assessed_by_actor_id=ids.human_owner,
    )


def _proposal(
    ids: FixtureIds,
    *,
    model_id: str,
    module_ids: tuple[str, ...] = (),
    promotions: tuple[TrustPromotion, ...] = (),
    claimed: ReadinessLevel = ReadinessLevel.CONTEXTUALIZED,
    evidenced: ReadinessLevel = ReadinessLevel.CONTEXTUALIZED,
    open_gap_ids: tuple[str, ...] = (),
    actor_id: str | None = None,
    workspace_object_id: str | None = None,
    tenant_id: str | None = None,
    at: datetime | None = None,
) -> WorkspaceCurationProposal:
    return WorkspaceCurationProposal(
        tenant_id=tenant_id or ids.tenant_alpha,
        workspace_object_id=workspace_object_id or ids.workspace_alpha_1,
        model_revision_id=model_id,
        module_ids_to_approve=module_ids,
        trust_promotions=promotions,
        claimed_readiness_level=claimed,
        dimensions_checked=("identity", "authority", "sources"),
        open_gap_ids=open_gap_ids,
        policy_basis="m2.curation.v1",
        evaluator_summary="curator approved binding content",
        evidenced_maximum_readiness=evidenced,
        actor_id=actor_id or ids.human_owner,
        at=at or NOW,
        confidence_summary="high for descriptive sections",
    )


def test_activate_curation_happy_path_with_promotion_and_supersede() -> None:
    conn, service, ids, _ = _service()
    first = _model(ids, revision=1)
    first_module = _module(ids)
    service.onboard(
        model=first,
        sources=(),
        modules=(first_module,),
        gaps=(),
        readiness=_readiness(ids, model_id=first.model_revision_id),
        actor_id=ids.human_owner,
        at=NOW,
    )
    first_activation = service.activate_curation(
        _proposal(
            ids,
            model_id=first.model_revision_id,
            module_ids=(first_module.module_id,),
            claimed=ReadinessLevel.DISCOVERED,
            evidenced=ReadinessLevel.DISCOVERED,
            at=LATER,
        ),
        authorized_human_promotion=False,
    )
    assert first_activation.approved_model.status is ModelRevisionStatus.APPROVED

    second = _model(ids, revision=2)
    source = _source(ids, locator="repo://README.md")
    module = _module(
        ids, key="architecture", revision=2, source_ids=(source.source_id,)
    )
    service.onboard(
        model=second,
        sources=(source,),
        modules=(module,),
        gaps=(),
        readiness=_readiness(ids, model_id=second.model_revision_id),
        actor_id=ids.human_owner,
        at=NOW,
    )
    discovered = service.discover_and_register_sources(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        observations=(
            ObservedSourcePath(
                locator="docs/architecture.md", observed_revision="rev-2"
            ),
        ),
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert discovered.registered_count == 1
    discovered_source_id = discovered.registered_source_ids[0]

    activate_at = LATER + timedelta(minutes=30)
    result = service.activate_curation(
        _proposal(
            ids,
            model_id=second.model_revision_id,
            module_ids=(module.module_id,),
            promotions=(
                TrustPromotion(
                    source_id=source.source_id,
                    to_trust=TrustClass.INSTRUCTION_AUTHORITY,
                ),
                TrustPromotion(
                    source_id=discovered_source_id,
                    to_trust=TrustClass.AUTHORITATIVE_REFERENCE,
                ),
            ),
            claimed=ReadinessLevel.CONTEXTUALIZED,
            evidenced=ReadinessLevel.CONTEXTUALIZED,
            at=activate_at,
        ),
        authorized_human_promotion=True,
    )

    assert result.approved_model.status is ModelRevisionStatus.APPROVED
    assert result.approved_model.model_revision_id == second.model_revision_id
    prior = service.get_model_revision(first.model_revision_id)
    assert prior is not None
    assert prior.status is ModelRevisionStatus.SUPERSEDED
    assert len(result.approved_modules) == 1
    assert result.approved_modules[0].approval_status is ModuleApprovalStatus.APPROVED
    stored_module = service.get_context_module(module.module_id)
    assert stored_module is not None
    assert stored_module.approval_status is ModuleApprovalStatus.APPROVED
    assert len(result.promoted_sources) == 2
    promoted = service.get_source(source.source_id)
    assert promoted is not None
    assert promoted.trust_class is TrustClass.INSTRUCTION_AUTHORITY
    assert promoted.instruction_authority is True
    auth_ref = service.get_source(discovered_source_id)
    assert auth_ref is not None
    assert auth_ref.trust_class is TrustClass.AUTHORITATIVE_REFERENCE
    latest = service.get_latest_readiness(
        ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
    )
    assert latest is not None
    assert latest.level is ReadinessLevel.CONTEXTUALIZED
    assert latest.model_revision_id == second.model_revision_id
    assert result.readiness.assessment_id == latest.assessment_id
    assert result.readiness.level is ReadinessLevel.CONTEXTUALIZED
    assert M2_EVENT_MODEL_APPROVED in result.event_types
    assert M2_EVENT_READINESS_ASSESSED in result.event_types
    events = {
        str(row[0])
        for row in conn.execute("SELECT event_type FROM gov_domain_events").fetchall()
    }
    assert M2_EVENT_MODEL_APPROVED in events
    assert M2_EVENT_READINESS_ASSESSED in events
    assert conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Mission'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Run'"
    ).fetchone()[0] == 0


def test_silent_instruction_authority_without_flag_fails() -> None:
    _conn, service, ids, _ = _service()
    model = _model(ids)
    source = _source(ids, trust=TrustClass.UNTRUSTED_REFERENCE)
    service.onboard(
        model=model,
        sources=(source,),
        modules=(),
        gaps=(),
        readiness=_readiness(ids, model_id=model.model_revision_id),
        actor_id=ids.human_owner,
        at=NOW,
    )
    proposal = _proposal(
        ids,
        model_id=model.model_revision_id,
        promotions=(
            TrustPromotion(
                source_id=source.source_id,
                to_trust=TrustClass.INSTRUCTION_AUTHORITY,
            ),
        ),
        claimed=ReadinessLevel.DISCOVERED,
        evidenced=ReadinessLevel.DISCOVERED,
    )
    with pytest.raises(MalformedCommandError, match="instruction_authority"):
        service.activate_curation(proposal, authorized_human_promotion=False)
    assert (
        service.get_model_revision(model.model_revision_id).status
        is ModelRevisionStatus.PROPOSED
    )
    assert (
        service.get_source(source.source_id).trust_class
        is TrustClass.UNTRUSTED_REFERENCE
    )


def test_validate_rejects_bad_ids_cross_tenant_readiness_and_gaps() -> None:
    _conn, service, ids, _ = _service()
    model = _model(ids)
    service.save_model_revision(model)

    with pytest.raises(NotFoundGovernanceError):
        service.validate_curation(
            _proposal(ids, model_id=generate_uuidv7()),
            authorized_human_promotion=False,
        )

    with pytest.raises(CrossTenantAccessError):
        service.validate_curation(
            _proposal(
                ids,
                model_id=model.model_revision_id,
                workspace_object_id=ids.workspace_beta_1,
            ),
            authorized_human_promotion=False,
        )

    with pytest.raises(MalformedCommandError, match="readiness cannot exceed"):
        validate_curation_proposal(
            _proposal(
                ids,
                model_id=model.model_revision_id,
                claimed=ReadinessLevel.GOVERNED,
                evidenced=ReadinessLevel.DISCOVERED,
            ),
            authorized_human_promotion=False,
        )

    with pytest.raises(MalformedCommandError, match="open knowledge gaps"):
        validate_curation_proposal(
            _proposal(
                ids,
                model_id=model.model_revision_id,
                claimed=ReadinessLevel.GOVERNED,
                evidenced=ReadinessLevel.GOVERNED,
                open_gap_ids=(generate_uuidv7(),),
            ),
            authorized_human_promotion=False,
        )

    with pytest.raises(NotFoundGovernanceError):
        service.validate_curation(
            _proposal(
                ids,
                model_id=model.model_revision_id,
                module_ids=(generate_uuidv7(),),
                claimed=ReadinessLevel.DISCOVERED,
                evidenced=ReadinessLevel.DISCOVERED,
            ),
            authorized_human_promotion=False,
        )


def test_missing_curate_permission_denied() -> None:
    _conn, service, ids, unauthorized = _service()
    model = _model(ids)
    service.save_model_revision(model)
    with pytest.raises(MissingAuthorityError):
        service.activate_curation(
            _proposal(
                ids,
                model_id=model.model_revision_id,
                actor_id=unauthorized,
                claimed=ReadinessLevel.DISCOVERED,
                evidenced=ReadinessLevel.DISCOVERED,
            ),
            authorized_human_promotion=False,
        )


def test_no_mission_or_run_writes_on_curation() -> None:
    conn, service, ids, _ = _service()
    model = _model(ids)
    service.save_model_revision(model)
    service.activate_curation(
        _proposal(
            ids,
            model_id=model.model_revision_id,
            claimed=ReadinessLevel.DISCOVERED,
            evidenced=ReadinessLevel.DISCOVERED,
        ),
        authorized_human_promotion=False,
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Mission'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Run'"
    ).fetchone()[0] == 0


def test_reactivating_already_approved_model_fails_cleanly() -> None:
    _conn, service, ids, _ = _service()
    model = _model(ids)
    service.save_model_revision(model)
    proposal = _proposal(
        ids,
        model_id=model.model_revision_id,
        claimed=ReadinessLevel.DISCOVERED,
        evidenced=ReadinessLevel.DISCOVERED,
    )
    service.activate_curation(proposal, authorized_human_promotion=False)
    with pytest.raises(MalformedCommandError, match="only proposed"):
        service.activate_curation(proposal, authorized_human_promotion=False)
