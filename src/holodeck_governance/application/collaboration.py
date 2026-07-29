"""Application seam for collaboration bindings, receipts, origins, and outbound."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from holodeck_governance.domain.collaboration.bindings import (
    CollaborationEndpoint,
    ExternalActorMapping,
)
from holodeck_governance.domain.collaboration.origins import TaskOrigin
from holodeck_governance.domain.collaboration.outbound import OutboundCollaborationMessage
from holodeck_governance.domain.collaboration.receipts import InboundEventReceipt
from holodeck_governance.domain.collaboration.types import LocationKind, ProcessingOutcome
from holodeck_governance.domain.errors import CrossTenantAccessError, MalformedCommandError
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.workspace.bindings import (
    CollaborationLocationBinding,
    RepositoryBinding,
    WorkspaceBindingStatus,
)
from holodeck_governance.domain.workspace.discovery import (
    WorkspaceDiscoveryOutcome,
    WorkspaceDiscoveryQuery,
    WorkspaceDiscoveryResult,
    evaluate_workspace_discovery,
)
from holodeck_governance.domain.workspace.genesis import (
    GenesisDecisionOutcome,
    WorkspaceGenesisDecision,
    WorkspaceGenesisProposal,
)


class CollaborationRepositoryPort(Protocol):
    def save_endpoint(self, endpoint: CollaborationEndpoint) -> None: ...

    def get_endpoint(self, endpoint_id: str) -> CollaborationEndpoint | None: ...

    def save_external_reference(self, ref: ExternalReference) -> None: ...

    def save_actor_mapping(self, mapping: ExternalActorMapping) -> None: ...

    def get_actor_mapping_by_external(
        self, *, tenant_id: str, provider: str, external_actor_id: str
    ) -> ExternalActorMapping | None: ...

    def get_inbound_receipt_by_external(
        self, *, tenant_id: str, provider: str, external_event_id: str
    ) -> InboundEventReceipt | None: ...

    def actor_may_intake(
        self, *, tenant_id: str, actor_id: str, at: datetime
    ) -> bool: ...

    def save_inbound_receipt(
        self,
        receipt: InboundEventReceipt,
        *,
        endpoint_id: str | None = None,
    ) -> InboundEventReceipt: ...

    def get_task_origin(self, object_id: str) -> TaskOrigin | None: ...

    def get_task_origin_by_external(
        self, *, tenant_id: str, provider: str, external_event_id: str
    ) -> TaskOrigin | None: ...

    def record_accepted_origin(
        self,
        *,
        origin: TaskOrigin,
        receipt: InboundEventReceipt,
        source_reference: ExternalReference,
        location_reference: ExternalReference,
        parent_location_reference: ExternalReference | None = None,
        endpoint_id: str | None = None,
    ) -> tuple[TaskOrigin, InboundEventReceipt, bool]: ...

    def enqueue_outbound_message(
        self, message: OutboundCollaborationMessage
    ) -> tuple[OutboundCollaborationMessage, str, bool]: ...

    def get_outbound_message(
        self, message_id: str
    ) -> OutboundCollaborationMessage | None: ...

    def save_repository_binding(self, binding: RepositoryBinding) -> None: ...

    def get_repository_binding(self, binding_id: str) -> RepositoryBinding | None: ...

    def resolve_active_repository_binding(
        self, *, tenant_id: str, provider: str, external_repository_id: str
    ) -> RepositoryBinding | None: ...

    def set_repository_binding_status(
        self, binding_id: str, *, tenant_id: str, status: WorkspaceBindingStatus
    ) -> RepositoryBinding: ...

    def save_collaboration_location_binding(
        self, binding: CollaborationLocationBinding
    ) -> None: ...

    def get_collaboration_location_binding(
        self, binding_id: str
    ) -> CollaborationLocationBinding | None: ...

    def resolve_active_collaboration_location_binding(
        self,
        *,
        tenant_id: str,
        endpoint_id: str,
        location_kind: LocationKind,
        external_location_id: str,
    ) -> CollaborationLocationBinding | None: ...

    def set_collaboration_location_binding_status(
        self, binding_id: str, *, tenant_id: str, status: WorkspaceBindingStatus
    ) -> CollaborationLocationBinding: ...

    def get_workspace_status(self, workspace_object_id: str) -> str | None: ...

    def get_workspace_genesis_proposal(
        self, proposal_id: str
    ) -> WorkspaceGenesisProposal | None: ...

    def get_open_workspace_genesis_proposal(
        self,
        *,
        tenant_id: str,
        endpoint_id: str,
        location_kind: LocationKind,
        external_location_id: str,
    ) -> WorkspaceGenesisProposal | None: ...

    def save_workspace_genesis_proposal(
        self, proposal: WorkspaceGenesisProposal
    ) -> None: ...

    def decide_workspace_genesis_proposal(
        self,
        *,
        proposal_id: str,
        tenant_id: str,
        outcome: GenesisDecisionOutcome,
        decided_at: datetime,
        decided_by_actor_id: str,
        rationale: str = "",
        repository_canonical_locator: str | None = None,
        repository_default_branch: str | None = None,
    ) -> WorkspaceGenesisProposal: ...


@dataclass(frozen=True, slots=True)
class RecordReceiptResult:
    receipt: InboundEventReceipt
    processing_outcome: ProcessingOutcome
    created: bool


@dataclass(frozen=True, slots=True)
class RecordOriginResult:
    origin: TaskOrigin
    receipt: InboundEventReceipt
    processing_outcome: ProcessingOutcome
    created: bool


@dataclass(frozen=True, slots=True)
class EnqueueOutboundResult:
    message: OutboundCollaborationMessage
    outbox_item_id: str
    created: bool


@dataclass(frozen=True, slots=True)
class CollaborationApplicationService:
    """Adapter-facing collaboration binding/receipt/origin/outbound seam.

    Uses the M1 bootstrap/admin persistence exception for create envelopes until
    typed ``collaboration.*.record`` command handlers exist. Never mutates
    task/run lifecycle state and never creates missions or approvals. Outbound
    enqueue creates durable outbox obligations only; adapter publish is separate.
    Workspace bindings enable deterministic intake lookup without treating
    channels or repositories as workspaces.
    """

    repository: CollaborationRepositoryPort

    def save_endpoint(self, endpoint: CollaborationEndpoint) -> CollaborationEndpoint:
        self.repository.save_endpoint(endpoint)
        return endpoint

    def get_endpoint(self, endpoint_id: str) -> CollaborationEndpoint | None:
        return self.repository.get_endpoint(endpoint_id)

    def save_external_reference(self, ref: ExternalReference) -> None:
        self.repository.save_external_reference(ref)

    def save_actor_mapping(self, mapping: ExternalActorMapping) -> ExternalActorMapping:
        self.repository.save_actor_mapping(mapping)
        return mapping

    def resolve_actor_mapping(
        self, *, tenant_id: str, provider: str, external_actor_id: str
    ) -> ExternalActorMapping | None:
        return self.repository.get_actor_mapping_by_external(
            tenant_id=tenant_id,
            provider=provider,
            external_actor_id=external_actor_id,
        )

    def get_inbound_receipt_by_external(
        self, *, tenant_id: str, provider: str, external_event_id: str
    ) -> InboundEventReceipt | None:
        return self.repository.get_inbound_receipt_by_external(
            tenant_id=tenant_id,
            provider=provider,
            external_event_id=external_event_id,
        )

    def actor_may_intake(
        self, *, tenant_id: str, actor_id: str, at: datetime
    ) -> bool:
        return self.repository.actor_may_intake(
            tenant_id=tenant_id, actor_id=actor_id, at=at
        )

    def save_repository_binding(self, binding: RepositoryBinding) -> RepositoryBinding:
        self.repository.save_repository_binding(binding)
        return binding

    def get_repository_binding(self, binding_id: str) -> RepositoryBinding | None:
        return self.repository.get_repository_binding(binding_id)

    def resolve_workspace_by_repository(
        self, *, tenant_id: str, provider: str, external_repository_id: str
    ) -> RepositoryBinding | None:
        """Deterministic intake lookup: active repository→workspace binding."""

        return self.repository.resolve_active_repository_binding(
            tenant_id=tenant_id,
            provider=provider,
            external_repository_id=external_repository_id,
        )

    def set_repository_binding_status(
        self, binding_id: str, *, tenant_id: str, status: WorkspaceBindingStatus
    ) -> RepositoryBinding:
        return self.repository.set_repository_binding_status(
            binding_id, tenant_id=tenant_id, status=status
        )

    def save_collaboration_location_binding(
        self, binding: CollaborationLocationBinding
    ) -> CollaborationLocationBinding:
        self.repository.save_collaboration_location_binding(binding)
        return binding

    def get_collaboration_location_binding(
        self, binding_id: str
    ) -> CollaborationLocationBinding | None:
        return self.repository.get_collaboration_location_binding(binding_id)

    def resolve_workspace_by_collaboration_location(
        self,
        *,
        tenant_id: str,
        endpoint_id: str,
        location_kind: LocationKind,
        external_location_id: str,
    ) -> CollaborationLocationBinding | None:
        """Deterministic intake lookup: active location→workspace binding."""

        return self.repository.resolve_active_collaboration_location_binding(
            tenant_id=tenant_id,
            endpoint_id=endpoint_id,
            location_kind=location_kind,
            external_location_id=external_location_id,
        )

    def set_collaboration_location_binding_status(
        self, binding_id: str, *, tenant_id: str, status: WorkspaceBindingStatus
    ) -> CollaborationLocationBinding:
        return self.repository.set_collaboration_location_binding_status(
            binding_id, tenant_id=tenant_id, status=status
        )

    def discover_workspace(
        self, query: WorkspaceDiscoveryQuery
    ) -> WorkspaceDiscoveryResult:
        """Explainably discover an eligible workspace for intake context."""

        endpoint = self.repository.get_endpoint(query.endpoint_id)
        if endpoint is None:
            raise MalformedCommandError(f"unknown collaboration endpoint {query.endpoint_id}")
        if endpoint.tenant_id != query.tenant_id:
            raise CrossTenantAccessError("discovery endpoint tenant mismatch")

        exact = self.repository.resolve_active_collaboration_location_binding(
            tenant_id=query.tenant_id,
            endpoint_id=query.endpoint_id,
            location_kind=query.location_kind,
            external_location_id=query.external_location_id,
        )
        parent = None
        if (
            query.parent_location_kind is not None
            and query.parent_external_location_id is not None
        ):
            parent = self.repository.resolve_active_collaboration_location_binding(
                tenant_id=query.tenant_id,
                endpoint_id=query.endpoint_id,
                location_kind=query.parent_location_kind,
                external_location_id=query.parent_external_location_id,
            )
        repository = None
        if (
            query.repository_provider is not None
            and query.external_repository_id is not None
        ):
            repository = self.repository.resolve_active_repository_binding(
                tenant_id=query.tenant_id,
                provider=query.repository_provider,
                external_repository_id=query.external_repository_id,
            )

        workspace_ids: set[str] = set()
        for binding in (exact, parent, repository):
            if binding is not None:
                workspace_ids.add(binding.workspace_object_id)
        workspace_statuses: dict[str, str] = {}
        for workspace_object_id in workspace_ids:
            status = self.repository.get_workspace_status(workspace_object_id)
            if status is None:
                workspace_statuses[workspace_object_id] = "missing"
            else:
                workspace_statuses[workspace_object_id] = status

        return evaluate_workspace_discovery(
            query,
            exact_location_binding=exact,
            parent_location_binding=parent,
            repository_binding=repository,
            workspace_statuses=workspace_statuses,
        )

    def propose_workspace_genesis(
        self,
        proposal: WorkspaceGenesisProposal,
        *,
        discovery_query: WorkspaceDiscoveryQuery | None = None,
    ) -> WorkspaceGenesisProposal:
        """Open a reversible genesis proposal for an unbound collaboration location."""

        from holodeck_governance.domain.workspace.genesis import GenesisProposalStatus

        if proposal.status is not GenesisProposalStatus.PROPOSED:
            raise MalformedCommandError("genesis proposals must be created as proposed")

        query = discovery_query or WorkspaceDiscoveryQuery(
            tenant_id=proposal.tenant_id,
            endpoint_id=proposal.endpoint_id,
            location_kind=proposal.location_kind,
            external_location_id=proposal.external_location_id,
            repository_provider=proposal.repository_provider,
            external_repository_id=proposal.external_repository_id,
        )
        discovery = self.discover_workspace(query)
        if discovery.outcome is not WorkspaceDiscoveryOutcome.UNBOUND:
            raise MalformedCommandError(
                "workspace genesis requires an unbound discovery outcome"
            )
        if not proposal.discovery_reason_codes:
            proposal = WorkspaceGenesisProposal(
                proposal_id=proposal.proposal_id,
                tenant_id=proposal.tenant_id,
                endpoint_id=proposal.endpoint_id,
                location_kind=proposal.location_kind,
                external_location_id=proposal.external_location_id,
                location_reference_id=proposal.location_reference_id,
                proposed_workspace_object_id=proposal.proposed_workspace_object_id,
                display_name=proposal.display_name,
                purpose_text=proposal.purpose_text,
                status=proposal.status,
                created_at=proposal.created_at,
                created_by_actor_id=proposal.created_by_actor_id,
                discovery_reason_codes=discovery.summary_reasons,
                repository_provider=proposal.repository_provider,
                external_repository_id=proposal.external_repository_id,
                repository_reference_id=proposal.repository_reference_id,
            )
        self.repository.save_workspace_genesis_proposal(proposal)
        return proposal

    def decide_workspace_genesis(
        self,
        decision: WorkspaceGenesisDecision,
        *,
        repository_canonical_locator: str | None = None,
        repository_default_branch: str | None = None,
    ) -> WorkspaceGenesisProposal:
        """Record a human decision; approve creates workspace + active bindings."""

        return self.repository.decide_workspace_genesis_proposal(
            proposal_id=decision.proposal_id,
            tenant_id=decision.tenant_id,
            outcome=decision.outcome,
            decided_at=decision.decided_at,
            decided_by_actor_id=decision.decided_by_actor_id,
            rationale=decision.rationale,
            repository_canonical_locator=repository_canonical_locator,
            repository_default_branch=repository_default_branch,
        )

    def get_workspace_genesis_proposal(
        self, proposal_id: str
    ) -> WorkspaceGenesisProposal | None:
        return self.repository.get_workspace_genesis_proposal(proposal_id)

    def record_inbound_receipt(
        self,
        receipt: InboundEventReceipt,
        *,
        source_reference: ExternalReference,
        endpoint_id: str | None = None,
    ) -> RecordReceiptResult:
        if source_reference.reference_id != receipt.signed_source_reference_id:
            raise MalformedCommandError(
                "source_reference.reference_id must match receipt"
            )
        if source_reference.tenant_id != receipt.tenant_id:
            raise CrossTenantAccessError("source reference tenant mismatch")
        if receipt.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN:
            raise MalformedCommandError(
                "use accept_task_origin for accepted_origin receipts"
            )

        self.repository.save_external_reference(source_reference)
        existing = self.repository.get_inbound_receipt_by_external(
            tenant_id=receipt.tenant_id,
            provider=receipt.provider,
            external_event_id=receipt.external_event_id,
        )
        if existing is not None:
            return RecordReceiptResult(
                receipt=existing,
                processing_outcome=ProcessingOutcome.DUPLICATE_REPLAY,
                created=False,
            )
        stored = self.repository.save_inbound_receipt(receipt, endpoint_id=endpoint_id)
        return RecordReceiptResult(
            receipt=stored,
            processing_outcome=stored.processing_outcome,
            created=True,
        )

    def accept_task_origin(
        self,
        *,
        origin: TaskOrigin,
        receipt: InboundEventReceipt,
        source_reference: ExternalReference,
        location_reference: ExternalReference,
        parent_location_reference: ExternalReference | None = None,
        endpoint_id: str | None = None,
    ) -> RecordOriginResult:
        """Record an explicit authorized intake as a durable task origin."""

        stored_origin, stored_receipt, created = self.repository.record_accepted_origin(
            origin=origin,
            receipt=receipt,
            source_reference=source_reference,
            location_reference=location_reference,
            parent_location_reference=parent_location_reference,
            endpoint_id=endpoint_id,
        )
        return RecordOriginResult(
            origin=stored_origin,
            receipt=stored_receipt,
            processing_outcome=(
                stored_receipt.processing_outcome
                if created
                else ProcessingOutcome.DUPLICATE_REPLAY
            ),
            created=created,
        )

    def get_task_origin(self, object_id: str) -> TaskOrigin | None:
        return self.repository.get_task_origin(object_id)

    def enqueue_outbound_status(
        self, message: OutboundCollaborationMessage
    ) -> EnqueueOutboundResult:
        """Enqueue correlated collaboration status through the durable outbox."""

        stored, outbox_item_id, created = self.repository.enqueue_outbound_message(
            message
        )
        return EnqueueOutboundResult(
            message=stored,
            outbox_item_id=outbox_item_id,
            created=created,
        )

    def get_outbound_message(
        self, message_id: str
    ) -> OutboundCollaborationMessage | None:
        return self.repository.get_outbound_message(message_id)
