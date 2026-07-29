"""M2-006 explainable workspace discovery and eligibility evaluation."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.collaboration import (
    BindingStatus,
    CollaborationEndpoint,
    LocationKind,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.records.workspace import WorkspaceRecord
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace import (
    CollaborationLocationBinding,
    RepositoryBinding,
    WorkspaceBindingStatus,
    WorkspaceDiscoveryOutcome,
    WorkspaceDiscoveryQuery,
    WorkspaceEligibility,
    evaluate_workspace_discovery,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.collaboration import SqliteCollaborationRepository
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.records import SqliteRecordRepository
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 8, 30, tzinfo=UTC)


def _service() -> tuple[sqlite3.Connection, CollaborationApplicationService, FixtureIds]:
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
    for workspace_id in (ids.workspace_alpha_1,):
        revisions.register_object(
            GovernanceObject(
                object_id=workspace_id,
                tenant_id=ids.tenant_alpha,
                object_type="Workspace",
                created_at=NOW,
                created_by_actor_id=ids.system_service,
            )
        )
    # Second alpha workspace for ambiguity cases.
    second = "01900000-0000-7000-8000-000000000013"
    revisions.register_object(
        GovernanceObject(
            object_id=second,
            tenant_id=ids.tenant_alpha,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    service = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )
    return conn, service, ids


def _second_workspace() -> str:
    return "01900000-0000-7000-8000-000000000013"


def _endpoint(ids: FixtureIds) -> CollaborationEndpoint:
    return CollaborationEndpoint(
        endpoint_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        external_endpoint_id="community-alpha",
        locator="memory://community-alpha",
        status=BindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )


def _ref(
    ids: FixtureIds, *, object_type: str, external_object_id: str, locator: str
) -> ExternalReference:
    return ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="memory",
        object_type=object_type,
        external_object_id=external_object_id,
        locator=locator,
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )


def _bind_location(
    service: CollaborationApplicationService,
    ids: FixtureIds,
    *,
    endpoint_id: str,
    workspace_object_id: str,
    location_kind: LocationKind,
    external_location_id: str,
) -> CollaborationLocationBinding:
    location = _ref(
        ids,
        object_type=f"conversation_{location_kind.value}",
        external_object_id=external_location_id,
        locator=f"memory://{external_location_id}",
    )
    service.save_external_reference(location)
    binding = CollaborationLocationBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=workspace_object_id,
        endpoint_id=endpoint_id,
        location_kind=location_kind,
        external_location_id=external_location_id,
        location_reference_id=location.reference_id,
        status=WorkspaceBindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_collaboration_location_binding(binding)
    return binding


def test_evaluate_unbound_when_no_bindings() -> None:
    query = WorkspaceDiscoveryQuery(
        tenant_id="01900000-0000-7000-8000-000000000001",
        endpoint_id="01900000-0000-7000-8000-0000000000e1",
        location_kind=LocationKind.THREAD,
        external_location_id="thread-1",
    )
    result = evaluate_workspace_discovery(
        query,
        exact_location_binding=None,
        parent_location_binding=None,
        repository_binding=None,
        workspace_statuses={},
    )
    assert result.outcome is WorkspaceDiscoveryOutcome.UNBOUND
    assert result.summary_reasons == ("unbound.no_active_bindings",)


def test_discover_exact_location_selects_workspace() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    _bind_location(
        service,
        ids,
        endpoint_id=endpoint.endpoint_id,
        workspace_object_id=ids.workspace_alpha_1,
        location_kind=LocationKind.THREAD,
        external_location_id="thread-1",
    )
    result = service.discover_workspace(
        WorkspaceDiscoveryQuery(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.THREAD,
            external_location_id="thread-1",
        )
    )
    assert result.outcome is WorkspaceDiscoveryOutcome.SELECTED
    assert result.selected_workspace_object_id == ids.workspace_alpha_1
    assert "location.exact" in result.summary_reasons


def test_discover_parent_fallback_when_exact_missing() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    _bind_location(
        service,
        ids,
        endpoint_id=endpoint.endpoint_id,
        workspace_object_id=ids.workspace_alpha_1,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-main",
    )
    result = service.discover_workspace(
        WorkspaceDiscoveryQuery(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.THREAD,
            external_location_id="thread-unbound",
            parent_location_kind=LocationKind.CHANNEL,
            parent_external_location_id="channel-main",
        )
    )
    assert result.outcome is WorkspaceDiscoveryOutcome.SELECTED
    assert result.selected_workspace_object_id == ids.workspace_alpha_1
    assert result.candidates[0].match_reasons == ("location.parent",)


def test_location_and_repository_agreement_ranks_higher() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    _bind_location(
        service,
        ids,
        endpoint_id=endpoint.endpoint_id,
        workspace_object_id=ids.workspace_alpha_1,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-main",
    )
    repo_ref = _ref(
        ids,
        object_type="repository",
        external_object_id="org/alpha",
        locator="https://example.test/org/alpha",
    )
    service.save_external_reference(repo_ref)
    service.save_repository_binding(
        RepositoryBinding(
            binding_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            provider="git",
            external_repository_id="org/alpha",
            canonical_locator=repo_ref.locator,
            default_branch="main",
            status=WorkspaceBindingStatus.ACTIVE,
            external_reference_id=repo_ref.reference_id,
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    result = service.discover_workspace(
        WorkspaceDiscoveryQuery(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.CHANNEL,
            external_location_id="channel-main",
            repository_provider="git",
            external_repository_id="org/alpha",
        )
    )
    assert result.outcome is WorkspaceDiscoveryOutcome.SELECTED
    assert "agreement.location_repository" in result.candidates[0].match_reasons


def test_ambiguous_when_location_and_repository_disagree() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    second = _second_workspace()
    _bind_location(
        service,
        ids,
        endpoint_id=endpoint.endpoint_id,
        workspace_object_id=ids.workspace_alpha_1,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-main",
    )
    repo_ref = _ref(
        ids,
        object_type="repository",
        external_object_id="org/other",
        locator="https://example.test/org/other",
    )
    service.save_external_reference(repo_ref)
    service.save_repository_binding(
        RepositoryBinding(
            binding_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            workspace_object_id=second,
            provider="git",
            external_repository_id="org/other",
            canonical_locator=repo_ref.locator,
            default_branch="main",
            status=WorkspaceBindingStatus.ACTIVE,
            external_reference_id=repo_ref.reference_id,
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    result = service.discover_workspace(
        WorkspaceDiscoveryQuery(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.CHANNEL,
            external_location_id="channel-main",
            repository_provider="git",
            external_repository_id="org/other",
        )
    )
    assert result.outcome is WorkspaceDiscoveryOutcome.AMBIGUOUS
    assert len([c for c in result.candidates if c.eligibility is WorkspaceEligibility.ELIGIBLE]) == 2
    assert any("conflict.location_repository" in c.match_reasons for c in result.candidates)


def test_suspended_workspace_is_ineligible_only() -> None:
    conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    _bind_location(
        service,
        ids,
        endpoint_id=endpoint.endpoint_id,
        workspace_object_id=ids.workspace_alpha_1,
        location_kind=LocationKind.THREAD,
        external_location_id="thread-1",
    )
    SqliteRecordRepository(conn).save_workspace(
        WorkspaceRecord(
            record_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            object_id=ids.workspace_alpha_1,
            revision=1,
            name="Alpha",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
            status="suspended",
        )
    )
    result = service.discover_workspace(
        WorkspaceDiscoveryQuery(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.THREAD,
            external_location_id="thread-1",
        )
    )
    assert result.outcome is WorkspaceDiscoveryOutcome.INELIGIBLE_ONLY
    assert result.candidates[0].eligibility is WorkspaceEligibility.INELIGIBLE
    assert result.candidates[0].eligibility_reasons == (
        "ineligible.workspace_status:suspended",
    )
