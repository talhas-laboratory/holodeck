"""Application seam for collaboration bindings, receipts, origins, and outbound."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from holodeck_governance.domain.collaboration.bindings import (
    CollaborationEndpoint,
    ExternalActorMapping,
)
from holodeck_governance.domain.collaboration.origins import TaskOrigin
from holodeck_governance.domain.collaboration.outbound import OutboundCollaborationMessage
from holodeck_governance.domain.collaboration.receipts import InboundEventReceipt
from holodeck_governance.domain.collaboration.types import ProcessingOutcome
from holodeck_governance.domain.errors import CrossTenantAccessError, MalformedCommandError
from holodeck_governance.domain.provenance.external_reference import ExternalReference


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
