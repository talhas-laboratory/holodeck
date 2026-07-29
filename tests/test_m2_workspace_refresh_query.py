"""M2-016 refresh orchestration, selective stale propagation, and query snapshot."""

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
    MissingAuthorityError,
    NotFoundGovernanceError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    M2_EVENT_CONTEXT_MODULE_STALE,
    M2_EVENT_SOURCE_STALE,
    REQUIRED_MODEL_SECTIONS,
    ContextModule,
    GapStatus,
    IntentSeed,
    KnowledgeGap,
    ModelRevisionStatus,
    ModelSectionState,
    ModuleApprovalStatus,
    ReadinessLevel,
    SectionCertainty,
    SourceRefreshObservation,
    SourceType,
    StaleStatus,
    TrustClass,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
    module_ids_depending_on_source,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.intelligence import (
    SqliteWorkspaceIntelligenceRepository,
)
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 19, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 29, 19, 30, tzinfo=UTC)


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
        (unauthorized, ids.tenant_alpha, "Reader", ActorKind.HUMAN),
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
        confidence_summary="refresh query fixture",
    )


def _source(
    ids: FixtureIds,
    *,
    locator: str = "repo://POLICY.md",
    observed_revision: str = "abc123",
    content_hash: str | None = "hash-abc",
) -> WorkspaceSource:
    return WorkspaceSource(
        source_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        source_type=SourceType.DOCUMENT,
        locator=locator,
        observed_revision=observed_revision,
        trust_class=TrustClass.ORDINARY_REFERENCE,
        owner_actor_id=ids.human_owner,
        sensitivity="public",
        refresh_policy="on_revision_change",
        observed_at=NOW,
        stale_status=StaleStatus.FRESH,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
        content_hash=content_hash,
        module_tags=("architecture",),
    )


def _module(
    ids: FixtureIds,
    *,
    key: str = "architecture",
    source_ids: tuple[str, ...] = (),
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
        revision=1,
        source_ids=source_ids,
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


def _readiness(ids: FixtureIds, *, model_id: str) -> WorkspaceReadinessAssessment:
    return WorkspaceReadinessAssessment(
        assessment_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        model_revision_id=model_id,
        level=ReadinessLevel.DISCOVERED,
        dimensions_checked=("identity", "sources"),
        open_gap_ids=(),
        policy_basis="m2.refresh.v1",
        evaluator_summary="discovered snapshot",
        assessed_at=NOW,
        assessed_by_actor_id=ids.human_owner,
    )


def test_module_ids_depending_on_source_helper() -> None:
    ids = FixtureIds()
    source_a = generate_uuidv7()
    source_b = generate_uuidv7()
    dependent = _module(ids, key="architecture", source_ids=(source_a,))
    unrelated = _module(ids, key="domain-language", source_ids=(source_b,))
    assert module_ids_depending_on_source(
        (dependent, unrelated), source_a
    ) == (dependent.module_id,)


def test_revision_change_stales_only_dependent_modules() -> None:
    conn, service, ids, _ = _service()
    source = _source(ids)
    other = _source(ids, locator="repo://README.md", observed_revision="r1")
    dependent = _module(ids, key="architecture", source_ids=(source.source_id,))
    unrelated = _module(ids, key="domain-language", source_ids=(other.source_id,))
    service.register_source(source)
    service.register_source(other)
    service.save_context_module(dependent)
    service.save_context_module(unrelated)

    result = service.refresh_sources(
        ids.workspace_alpha_1,
        tenant_id=ids.tenant_alpha,
        observations=(
            SourceRefreshObservation(
                source_id=source.source_id,
                new_observed_revision="def456",
                content_hash="hash-def",
            ),
        ),
        actor_id=ids.human_owner,
        at=LATER,
    )
    assert result.refreshed_source_ids == (source.source_id,)
    assert result.skipped_unchanged == ()
    assert result.staled_module_ids == (dependent.module_id,)

    refreshed = service.get_source(source.source_id)
    assert refreshed is not None
    assert refreshed.observed_revision == "def456"
    assert refreshed.content_hash == "hash-def"
    assert refreshed.stale_status is StaleStatus.STALE
    assert service.get_context_module(dependent.module_id).freshness is StaleStatus.STALE
    assert service.get_context_module(unrelated.module_id).freshness is StaleStatus.FRESH
    assert service.get_source(other.source_id).stale_status is StaleStatus.FRESH

    events = [
        str(row[0])
        for row in conn.execute("SELECT event_type FROM gov_domain_events").fetchall()
    ]
    assert M2_EVENT_SOURCE_STALE in events
    assert events.count(M2_EVENT_CONTEXT_MODULE_STALE) == 1


def test_same_revision_refresh_is_noop() -> None:
    conn, service, ids, _ = _service()
    source = _source(ids, observed_revision="abc123")
    dependent = _module(ids, source_ids=(source.source_id,))
    service.register_source(source)
    service.save_context_module(dependent)

    result = service.refresh_sources(
        ids.workspace_alpha_1,
        tenant_id=ids.tenant_alpha,
        observations=(
            SourceRefreshObservation(
                source_id=source.source_id,
                new_observed_revision="abc123",
                content_hash="hash-new",
            ),
        ),
        actor_id=ids.human_owner,
        at=LATER,
    )
    assert result.refreshed_source_ids == ()
    assert result.skipped_unchanged == (source.source_id,)
    assert result.staled_module_ids == ()
    stored = service.get_source(source.source_id)
    assert stored is not None
    assert stored.stale_status is StaleStatus.FRESH
    assert stored.content_hash == "hash-abc"
    assert service.get_context_module(dependent.module_id).freshness is StaleStatus.FRESH
    events = [
        str(row[0])
        for row in conn.execute("SELECT event_type FROM gov_domain_events").fetchall()
    ]
    assert M2_EVENT_SOURCE_STALE not in events
    assert M2_EVENT_CONTEXT_MODULE_STALE not in events


def test_propagate_source_stale_resolves_dependents() -> None:
    _conn, service, ids, _ = _service()
    source = _source(ids)
    dependent = _module(ids, key="architecture", source_ids=(source.source_id,))
    unrelated = _module(ids, key="domain-language")
    service.register_source(source)
    service.save_context_module(dependent)
    service.save_context_module(unrelated)

    service.propagate_source_stale(
        source.source_id,
        tenant_id=ids.tenant_alpha,
        actor_id=ids.human_owner,
        at=LATER,
    )
    assert service.get_source(source.source_id).stale_status is StaleStatus.STALE
    assert service.get_context_module(dependent.module_id).freshness is StaleStatus.STALE
    assert service.get_context_module(unrelated.module_id).freshness is StaleStatus.FRESH


def test_query_workspace_intelligence_snapshot() -> None:
    _conn, service, ids, unauthorized = _service()
    model = _model(ids, revision=1)
    service.save_model_revision(model)
    approved = service.approve_model_revision(
        model.model_revision_id,
        tenant_id=ids.tenant_alpha,
        approved_by_actor_id=ids.human_owner,
        approved_at=NOW,
    )
    proposed = _model(ids, revision=2)
    service.save_model_revision(proposed)
    source = _source(ids)
    service.register_source(source)
    module = _module(ids, source_ids=(source.source_id,))
    service.save_context_module(module)
    gap = _gap(ids)
    service.save_knowledge_gap(gap)
    readiness = _readiness(ids, model_id=approved.model_revision_id)
    service.save_readiness_assessment(readiness)

    service.refresh_sources(
        ids.workspace_alpha_1,
        tenant_id=ids.tenant_alpha,
        observations=(
            SourceRefreshObservation(
                locator=source.locator,
                new_observed_revision="zzz999",
            ),
        ),
        actor_id=ids.human_owner,
        at=LATER,
    )

    snapshot = service.query_workspace_intelligence(
        ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
    )
    assert snapshot.model is not None
    assert snapshot.model.model_revision_id == approved.model_revision_id
    assert snapshot.model.status is ModelRevisionStatus.APPROVED
    assert len(snapshot.sources) == 1
    assert len(snapshot.modules) == 1
    assert [gap.gap_id for gap in snapshot.open_gaps] == [gap.gap_id]
    assert snapshot.latest_readiness is not None
    assert snapshot.latest_readiness.assessment_id == readiness.assessment_id
    assert snapshot.stale_source_ids == (source.source_id,)
    assert snapshot.stale_module_ids == (module.module_id,)

    # Reader without curate can still query (and list/get continue to work).
    listed = service.list_sources(ids.workspace_alpha_1, tenant_id=ids.tenant_alpha)
    assert len(listed) == 1
    assert service.get_source(source.source_id) is not None
    reader_snapshot = service.query_workspace_intelligence(
        ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
    )
    assert reader_snapshot.model is not None
    assert unauthorized  # fixture actor exists without curate grant


def test_refresh_requires_curate_unknown_source_and_cross_tenant() -> None:
    conn, service, ids, unauthorized = _service()
    source = _source(ids)
    service.register_source(source)

    with pytest.raises(MissingAuthorityError):
        service.refresh_sources(
            ids.workspace_alpha_1,
            tenant_id=ids.tenant_alpha,
            observations=(
                SourceRefreshObservation(
                    source_id=source.source_id,
                    new_observed_revision="new-rev",
                ),
            ),
            actor_id=unauthorized,
            at=LATER,
        )
    with pytest.raises(MissingAuthorityError):
        service.propagate_source_stale(
            source.source_id,
            tenant_id=ids.tenant_alpha,
            actor_id=unauthorized,
            at=LATER,
        )
    with pytest.raises(NotFoundGovernanceError):
        service.refresh_sources(
            ids.workspace_alpha_1,
            tenant_id=ids.tenant_alpha,
            observations=(
                SourceRefreshObservation(
                    source_id=generate_uuidv7(),
                    new_observed_revision="new-rev",
                ),
            ),
            actor_id=ids.human_owner,
            at=LATER,
        )
    with pytest.raises(CrossTenantAccessError):
        service.query_workspace_intelligence(
            ids.workspace_beta_1, tenant_id=ids.tenant_alpha
        )
    with pytest.raises(CrossTenantAccessError):
        service.refresh_sources(
            ids.workspace_beta_1,
            tenant_id=ids.tenant_alpha,
            observations=(
                SourceRefreshObservation(
                    source_id=source.source_id,
                    new_observed_revision="new-rev",
                ),
            ),
            actor_id=ids.human_owner,
            at=LATER,
        )

    assert conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Mission'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Run'"
    ).fetchone()[0] == 0
