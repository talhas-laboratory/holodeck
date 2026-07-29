"""M2-005 repository and collaboration-location workspace bindings."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.collaboration import (
    BindingStatus,
    CollaborationEndpoint,
    LocationKind,
)
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    RevisionImmutableError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace import (
    CollaborationLocationBinding,
    RepositoryBinding,
    WorkspaceBindingStatus,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.collaboration import SqliteCollaborationRepository
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
)
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 7, 30, tzinfo=UTC)


def _service() -> tuple[sqlite3.Connection, CollaborationApplicationService, FixtureIds]:
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
    for actor_id, tenant_id, name in (
        (ids.human_owner, ids.tenant_alpha, "Owner"),
        (ids.system_service, ids.tenant_alpha, "System"),
        (ids.human_reviewer, ids.tenant_beta, "Beta"),
    ):
        auth.save_actor(
            Actor(
                actor_id=actor_id,
                tenant_id=tenant_id,
                kind=ActorKind.HUMAN if actor_id != ids.system_service else ActorKind.SERVICE,
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
    service = CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )
    return conn, service, ids


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
    ids: FixtureIds,
    *,
    object_type: str,
    external_object_id: str,
    locator: str,
    tenant_id: str | None = None,
) -> ExternalReference:
    return ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=tenant_id or ids.tenant_alpha,
        provider="memory",
        object_type=object_type,
        external_object_id=external_object_id,
        locator=locator,
        observed_at=NOW,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )


def test_migrate_v16_creates_workspace_binding_tables() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    assert governance_schema_version(conn) == 24
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "gov_repository_bindings" in tables
    assert "gov_collaboration_location_bindings" in tables


def test_repository_binding_save_and_active_lookup() -> None:
    _conn, service, ids = _service()
    repo_ref = _ref(
        ids,
        object_type="repository",
        external_object_id="org/alpha",
        locator="https://example.test/org/alpha",
    )
    service.save_external_reference(repo_ref)
    binding = RepositoryBinding(
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
    service.save_repository_binding(binding)
    resolved = service.resolve_workspace_by_repository(
        tenant_id=ids.tenant_alpha,
        provider="git",
        external_repository_id="org/alpha",
    )
    assert resolved is not None
    assert resolved.workspace_object_id == ids.workspace_alpha_1
    assert service.get_repository_binding(binding.binding_id) == binding


def test_collaboration_location_binding_save_and_active_lookup() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    location = _ref(
        ids,
        object_type="conversation_channel",
        external_object_id="channel-main",
        locator="memory://channels/main",
    )
    service.save_external_reference(location)
    binding = CollaborationLocationBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-main",
        location_reference_id=location.reference_id,
        status=WorkspaceBindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_collaboration_location_binding(binding)
    resolved = service.resolve_workspace_by_collaboration_location(
        tenant_id=ids.tenant_alpha,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-main",
    )
    assert resolved is not None
    assert resolved.workspace_object_id == ids.workspace_alpha_1
    assert resolved.binding_id == binding.binding_id


def test_proposed_and_retired_bindings_do_not_resolve_for_intake() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    location = _ref(
        ids,
        object_type="conversation_thread",
        external_object_id="thread-1",
        locator="memory://threads/1",
    )
    service.save_external_reference(location)
    proposed = CollaborationLocationBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.THREAD,
        external_location_id="thread-1",
        location_reference_id=location.reference_id,
        status=WorkspaceBindingStatus.PROPOSED,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_collaboration_location_binding(proposed)
    assert (
        service.resolve_workspace_by_collaboration_location(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.THREAD,
            external_location_id="thread-1",
        )
        is None
    )
    active = service.set_collaboration_location_binding_status(
        proposed.binding_id,
        tenant_id=ids.tenant_alpha,
        status=WorkspaceBindingStatus.ACTIVE,
    )
    assert active.status is WorkspaceBindingStatus.ACTIVE
    assert (
        service.resolve_workspace_by_collaboration_location(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.THREAD,
            external_location_id="thread-1",
        )
        is not None
    )
    service.set_collaboration_location_binding_status(
        proposed.binding_id,
        tenant_id=ids.tenant_alpha,
        status=WorkspaceBindingStatus.RETIRED,
    )
    assert (
        service.resolve_workspace_by_collaboration_location(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.THREAD,
            external_location_id="thread-1",
        )
        is None
    )


def test_duplicate_repository_binding_natural_key_rejected() -> None:
    _conn, service, ids = _service()
    repo_ref = _ref(
        ids,
        object_type="repository",
        external_object_id="org/dup",
        locator="https://example.test/org/dup",
    )
    service.save_external_reference(repo_ref)
    first = RepositoryBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        provider="git",
        external_repository_id="org/dup",
        canonical_locator=repo_ref.locator,
        default_branch="main",
        status=WorkspaceBindingStatus.ACTIVE,
        external_reference_id=repo_ref.reference_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_repository_binding(first)
    with pytest.raises(RevisionImmutableError):
        service.save_repository_binding(
            RepositoryBinding(
                binding_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_alpha_1,
                provider="git",
                external_repository_id="org/dup",
                canonical_locator=repo_ref.locator,
                default_branch="main",
                status=WorkspaceBindingStatus.ACTIVE,
                external_reference_id=repo_ref.reference_id,
                created_at=NOW,
                created_by_actor_id=ids.system_service,
            )
        )


def test_retire_then_rebind_repository_to_new_workspace() -> None:
    conn, service, ids = _service()
    workspace_alpha_2 = generate_uuidv7()
    SqliteRevisionRepository(conn).register_object(
        GovernanceObject(
            object_id=workspace_alpha_2,
            tenant_id=ids.tenant_alpha,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    repo_ref = _ref(
        ids,
        object_type="repository",
        external_object_id="org/rebind",
        locator="https://example.test/org/rebind",
    )
    service.save_external_reference(repo_ref)
    old = RepositoryBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        provider="git",
        external_repository_id="org/rebind",
        canonical_locator=repo_ref.locator,
        default_branch="main",
        status=WorkspaceBindingStatus.ACTIVE,
        external_reference_id=repo_ref.reference_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_repository_binding(old)
    service.set_repository_binding_status(
        old.binding_id,
        tenant_id=ids.tenant_alpha,
        status=WorkspaceBindingStatus.RETIRED,
    )
    replacement = RepositoryBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=workspace_alpha_2,
        provider="git",
        external_repository_id="org/rebind",
        canonical_locator=repo_ref.locator,
        default_branch="main",
        status=WorkspaceBindingStatus.ACTIVE,
        external_reference_id=repo_ref.reference_id,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_repository_binding(replacement)
    resolved = service.resolve_workspace_by_repository(
        tenant_id=ids.tenant_alpha,
        provider="git",
        external_repository_id="org/rebind",
    )
    assert resolved is not None
    assert resolved.binding_id == replacement.binding_id
    assert resolved.workspace_object_id == workspace_alpha_2
    assert (
        conn.execute("SELECT COUNT(*) FROM gov_repository_bindings").fetchone()[0] == 2
    )


def test_retire_then_rebind_collaboration_location() -> None:
    conn, service, ids = _service()
    workspace_alpha_2 = generate_uuidv7()
    SqliteRevisionRepository(conn).register_object(
        GovernanceObject(
            object_id=workspace_alpha_2,
            tenant_id=ids.tenant_alpha,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    location = _ref(
        ids,
        object_type="conversation_channel",
        external_object_id="channel-rebind",
        locator="memory://channels/rebind",
    )
    service.save_external_reference(location)
    old = CollaborationLocationBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-rebind",
        location_reference_id=location.reference_id,
        status=WorkspaceBindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_collaboration_location_binding(old)
    service.set_collaboration_location_binding_status(
        old.binding_id,
        tenant_id=ids.tenant_alpha,
        status=WorkspaceBindingStatus.RETIRED,
    )
    assert (
        service.resolve_workspace_by_collaboration_location(
            tenant_id=ids.tenant_alpha,
            endpoint_id=endpoint.endpoint_id,
            location_kind=LocationKind.CHANNEL,
            external_location_id="channel-rebind",
        )
        is None
    )
    replacement = CollaborationLocationBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=workspace_alpha_2,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-rebind",
        location_reference_id=location.reference_id,
        status=WorkspaceBindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_collaboration_location_binding(replacement)
    resolved = service.resolve_workspace_by_collaboration_location(
        tenant_id=ids.tenant_alpha,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-rebind",
    )
    assert resolved is not None
    assert resolved.binding_id == replacement.binding_id
    assert resolved.workspace_object_id == workspace_alpha_2
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gov_collaboration_location_bindings"
        ).fetchone()[0]
        == 2
    )


def test_two_active_collaboration_location_bindings_rejected() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    location = _ref(
        ids,
        object_type="conversation_channel",
        external_object_id="channel-two-active",
        locator="memory://channels/two-active",
    )
    service.save_external_reference(location)
    first = CollaborationLocationBinding(
        binding_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-two-active",
        location_reference_id=location.reference_id,
        status=WorkspaceBindingStatus.ACTIVE,
        created_at=NOW,
        created_by_actor_id=ids.system_service,
    )
    service.save_collaboration_location_binding(first)
    with pytest.raises(RevisionImmutableError):
        service.save_collaboration_location_binding(
            CollaborationLocationBinding(
                binding_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_alpha_1,
                endpoint_id=endpoint.endpoint_id,
                location_kind=LocationKind.CHANNEL,
                external_location_id="channel-two-active",
                location_reference_id=location.reference_id,
                status=WorkspaceBindingStatus.ACTIVE,
                created_at=NOW,
                created_by_actor_id=ids.system_service,
            )
        )


def test_cross_tenant_workspace_binding_rejected() -> None:
    _conn, service, ids = _service()
    repo_ref = _ref(
        ids,
        object_type="repository",
        external_object_id="org/cross",
        locator="https://example.test/org/cross",
    )
    service.save_external_reference(repo_ref)
    with pytest.raises(CrossTenantAccessError):
        service.save_repository_binding(
            RepositoryBinding(
                binding_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                workspace_object_id=ids.workspace_beta_1,
                provider="git",
                external_repository_id="org/cross",
                canonical_locator=repo_ref.locator,
                default_branch="main",
                status=WorkspaceBindingStatus.ACTIVE,
                external_reference_id=repo_ref.reference_id,
                created_at=NOW,
                created_by_actor_id=ids.system_service,
            )
        )
