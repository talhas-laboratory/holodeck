"""M2-007 reversible workspace-genesis proposals and decisions."""

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
    IdempotencyConflictError,
    MalformedCommandError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.workspace import (
    GenesisDecisionOutcome,
    GenesisProposalStatus,
    WorkspaceBindingStatus,
    WorkspaceGenesisDecision,
    WorkspaceGenesisProposal,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.collaboration import SqliteCollaborationRepository
from holodeck_governance.storage.sqlite.migrations import (
    governance_schema_version,
    migrate_governance,
)
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 9, 15, tzinfo=UTC)


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
    for actor_id, tenant_id, name, kind in (
        (ids.human_owner, ids.tenant_alpha, "Owner", ActorKind.HUMAN),
        (ids.system_service, ids.tenant_alpha, "System", ActorKind.SERVICE),
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


def _open_proposal(
    service: CollaborationApplicationService,
    ids: FixtureIds,
    *,
    endpoint: CollaborationEndpoint,
    external_location_id: str = "channel-new",
) -> WorkspaceGenesisProposal:
    location = _ref(
        ids,
        object_type="conversation_channel",
        external_object_id=external_location_id,
        locator=f"memory://{external_location_id}",
    )
    service.save_external_reference(location)
    proposal = WorkspaceGenesisProposal(
        proposal_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.CHANNEL,
        external_location_id=external_location_id,
        location_reference_id=location.reference_id,
        proposed_workspace_object_id=generate_uuidv7(),
        display_name="Alpha Channel Workspace",
        purpose_text="Govern work requested from this channel",
        status=GenesisProposalStatus.PROPOSED,
        created_at=NOW,
        created_by_actor_id=ids.human_owner,
    )
    return service.propose_workspace_genesis(proposal)


def test_migrate_v17_creates_genesis_table() -> None:
    conn = sqlite3.connect(":memory:")
    migrate_governance(conn)
    assert governance_schema_version(conn) == 17
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "gov_workspace_genesis_proposals" in tables


def test_propose_and_approve_creates_workspace_and_binding() -> None:
    conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    proposal = _open_proposal(service, ids, endpoint=endpoint)
    assert proposal.status is GenesisProposalStatus.PROPOSED
    assert "unbound.no_active_bindings" in proposal.discovery_reason_codes

    decided = service.decide_workspace_genesis(
        WorkspaceGenesisDecision(
            proposal_id=proposal.proposal_id,
            tenant_id=ids.tenant_alpha,
            outcome=GenesisDecisionOutcome.APPROVE,
            decided_at=NOW,
            decided_by_actor_id=ids.human_owner,
            rationale="Approved for intake",
        )
    )
    assert decided.status is GenesisProposalStatus.APPROVED
    assert decided.decision_outcome is GenesisDecisionOutcome.APPROVE
    workspace = conn.execute(
        "SELECT name, status FROM gov_workspaces WHERE object_id = ?",
        (proposal.proposed_workspace_object_id,),
    ).fetchone()
    assert workspace is not None
    assert str(workspace["name"]) == "Alpha Channel Workspace"
    assert str(workspace["status"]) == "active"
    binding = service.resolve_workspace_by_collaboration_location(
        tenant_id=ids.tenant_alpha,
        endpoint_id=endpoint.endpoint_id,
        location_kind=LocationKind.CHANNEL,
        external_location_id="channel-new",
    )
    assert binding is not None
    assert binding.workspace_object_id == proposal.proposed_workspace_object_id
    assert binding.status is WorkspaceBindingStatus.ACTIVE


def test_reject_and_withdraw_create_no_workspace() -> None:
    conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    rejected = _open_proposal(
        service, ids, endpoint=endpoint, external_location_id="channel-reject"
    )
    service.decide_workspace_genesis(
        WorkspaceGenesisDecision(
            proposal_id=rejected.proposal_id,
            tenant_id=ids.tenant_alpha,
            outcome=GenesisDecisionOutcome.REJECT,
            decided_at=NOW,
            decided_by_actor_id=ids.human_owner,
            rationale="Not needed",
        )
    )
    withdrawn = _open_proposal(
        service, ids, endpoint=endpoint, external_location_id="channel-withdraw"
    )
    service.decide_workspace_genesis(
        WorkspaceGenesisDecision(
            proposal_id=withdrawn.proposal_id,
            tenant_id=ids.tenant_alpha,
            outcome=GenesisDecisionOutcome.WITHDRAW,
            decided_at=NOW,
            decided_by_actor_id=ids.human_owner,
        )
    )
    assert conn.execute("SELECT COUNT(*) FROM gov_workspaces").fetchone()[0] == 0
    assert (
        conn.execute("SELECT COUNT(*) FROM gov_collaboration_location_bindings").fetchone()[
            0
        ]
        == 0
    )


def test_duplicate_open_proposal_rejected() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    first = _open_proposal(
        service, ids, endpoint=endpoint, external_location_id="channel-dup"
    )
    with pytest.raises(IdempotencyConflictError):
        service.propose_workspace_genesis(
            WorkspaceGenesisProposal(
                proposal_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                endpoint_id=endpoint.endpoint_id,
                location_kind=LocationKind.CHANNEL,
                external_location_id="channel-dup",
                location_reference_id=first.location_reference_id,
                proposed_workspace_object_id=generate_uuidv7(),
                display_name="Dup",
                purpose_text="Should fail",
                status=GenesisProposalStatus.PROPOSED,
                created_at=NOW,
                created_by_actor_id=ids.human_owner,
            )
        )


def test_cannot_propose_when_binding_already_exists() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    # First approve a workspace for the location.
    proposal = _open_proposal(
        service, ids, endpoint=endpoint, external_location_id="channel-bound"
    )
    service.decide_workspace_genesis(
        WorkspaceGenesisDecision(
            proposal_id=proposal.proposal_id,
            tenant_id=ids.tenant_alpha,
            outcome=GenesisDecisionOutcome.APPROVE,
            decided_at=NOW,
            decided_by_actor_id=ids.human_owner,
        )
    )
    with pytest.raises(MalformedCommandError):
        service.propose_workspace_genesis(
            WorkspaceGenesisProposal(
                proposal_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                endpoint_id=endpoint.endpoint_id,
                location_kind=LocationKind.CHANNEL,
                external_location_id="channel-bound",
                location_reference_id=proposal.location_reference_id,
                proposed_workspace_object_id=generate_uuidv7(),
                display_name="Again",
                purpose_text="Should fail because selected",
                status=GenesisProposalStatus.PROPOSED,
                created_at=NOW,
                created_by_actor_id=ids.human_owner,
            )
        )


def test_cannot_decide_closed_proposal() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    proposal = _open_proposal(
        service, ids, endpoint=endpoint, external_location_id="channel-closed"
    )
    service.decide_workspace_genesis(
        WorkspaceGenesisDecision(
            proposal_id=proposal.proposal_id,
            tenant_id=ids.tenant_alpha,
            outcome=GenesisDecisionOutcome.WITHDRAW,
            decided_at=NOW,
            decided_by_actor_id=ids.human_owner,
        )
    )
    with pytest.raises(MalformedCommandError):
        service.decide_workspace_genesis(
            WorkspaceGenesisDecision(
                proposal_id=proposal.proposal_id,
                tenant_id=ids.tenant_alpha,
                outcome=GenesisDecisionOutcome.APPROVE,
                decided_at=NOW,
                decided_by_actor_id=ids.human_owner,
            )
        )


def test_cross_tenant_genesis_proposal_rejected() -> None:
    _conn, service, ids = _service()
    endpoint = _endpoint(ids)
    service.save_endpoint(endpoint)
    location = _ref(
        ids,
        object_type="conversation_channel",
        external_object_id="channel-xtenant",
        locator="memory://channel-xtenant",
    )
    service.save_external_reference(location)
    with pytest.raises(CrossTenantAccessError):
        service.propose_workspace_genesis(
            WorkspaceGenesisProposal(
                proposal_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                endpoint_id=endpoint.endpoint_id,
                location_kind=LocationKind.CHANNEL,
                external_location_id="channel-xtenant",
                location_reference_id=location.reference_id,
                proposed_workspace_object_id=generate_uuidv7(),
                display_name="XTenant",
                purpose_text="Should fail",
                status=GenesisProposalStatus.PROPOSED,
                created_at=NOW,
                created_by_actor_id=ids.human_reviewer,
            )
        )
