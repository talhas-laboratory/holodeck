"""End-to-end collaboration intake orchestration over a replaceable adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping

from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.domain.collaboration.adapter import (
    CollaborationAdapter,
    CollaborationAdapterAuthError,
)
from holodeck_governance.domain.collaboration.inbound import NormalizedInboundEvent
from holodeck_governance.domain.collaboration.intake import parse_intake_command
from holodeck_governance.domain.collaboration.origins import TaskOrigin
from holodeck_governance.domain.collaboration.outbound import (
    OutboundCollaborationMessage,
    outbound_idempotency_key,
)
from holodeck_governance.domain.collaboration.receipts import InboundEventReceipt
from holodeck_governance.domain.collaboration.types import (
    ProcessingOutcome,
    VerificationResult,
)
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    MalformedCommandError,
    MissingAuthorityError,
)
from holodeck_governance.domain.ids import generate_uuidv7


@dataclass(frozen=True, slots=True)
class IntakeHandleResult:
    """Outcome of one inbound collaboration handle attempt."""

    processing_outcome: ProcessingOutcome
    verification_result: VerificationResult | None = None
    receipt: InboundEventReceipt | None = None
    origin: TaskOrigin | None = None
    outbound_message: OutboundCollaborationMessage | None = None
    outbound_ack: Mapping[str, str] | None = None
    outbox_item_id: str | None = None
    created: bool = False
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CollaborationIntakeOrchestrator:
    """Wire adapter normalize/verify to Holodeck receipt/origin/outbox/publish.

    Holodeck remains the system of record. Adapter publish acknowledgements are
    delivery metadata only. Accepted origin and correlated outbound/outbox are
    committed atomically; retries repair a missing outbound if needed.
    """

    adapter: CollaborationAdapter
    collaboration: CollaborationApplicationService
    created_by_actor_id: str
    clock: Callable[[], datetime]
    id_factory: Callable[[], str] = generate_uuidv7

    def handle_inbound(
        self, raw_provider_payload: Mapping[str, Any]
    ) -> IntakeHandleResult:
        try:
            event = self.adapter.normalize_inbound(raw_provider_payload)
            verified = self.adapter.verify_and_map_actor(event)
        except CollaborationAdapterAuthError as exc:
            return IntakeHandleResult(
                processing_outcome=ProcessingOutcome.AUTH_FAILED,
                verification_result=exc.verification_result,
                reason_codes=("reason.authentication_failed",),
            )

        existing = self.collaboration.get_inbound_receipt_by_external(
            tenant_id=event.tenant_id,
            provider=event.provider,
            external_event_id=event.external_event_id,
        )
        if existing is not None:
            return self._replay_or_repair_accepted(existing=existing, event=event)

        intake = parse_intake_command(event.body_text)
        mapping = self.collaboration.resolve_actor_mapping(
            tenant_id=event.tenant_id,
            provider=event.provider,
            external_actor_id=verified.external_identity.external_object_id,
        )
        endpoint_id = event.location.endpoint_id
        now = self.clock()

        if mapping is None:
            return self._record_non_origin(
                event=event,
                outcome=ProcessingOutcome.REJECTED,
                reason_codes=("reason.missing_actor_mapping",),
                endpoint_id=endpoint_id,
                at=now,
            )

        if endpoint_id is None:
            return self._record_non_origin(
                event=event,
                outcome=ProcessingOutcome.REJECTED,
                reason_codes=("reason.missing_endpoint",),
                endpoint_id=None,
                at=now,
                mapping_id=mapping.mapping_id,
                external_actor_id=mapping.external_actor_id,
            )

        endpoint = self.collaboration.get_endpoint(endpoint_id)
        if endpoint is None:
            return self._record_non_origin(
                event=event,
                outcome=ProcessingOutcome.REJECTED,
                reason_codes=("reason.unknown_endpoint",),
                endpoint_id=endpoint_id,
                at=now,
                mapping_id=mapping.mapping_id,
                external_actor_id=mapping.external_actor_id,
            )
        if endpoint.tenant_id != event.tenant_id:
            return self._record_non_origin(
                event=event,
                outcome=ProcessingOutcome.REJECTED,
                reason_codes=("reason.cross_tenant_denied",),
                endpoint_id=endpoint_id,
                at=now,
                mapping_id=mapping.mapping_id,
                external_actor_id=mapping.external_actor_id,
            )
        if mapping.endpoint_id != endpoint_id or mapping.actor_id != verified.actor_id:
            return self._record_non_origin(
                event=event,
                outcome=ProcessingOutcome.REJECTED,
                reason_codes=("reason.actor_mapping_mismatch",),
                endpoint_id=endpoint_id,
                at=now,
                mapping_id=mapping.mapping_id,
                external_actor_id=mapping.external_actor_id,
            )

        if not intake.is_explicit_intake:
            return self._record_non_origin(
                event=event,
                outcome=ProcessingOutcome.IGNORED_NON_INTAKE,
                reason_codes=("reason.non_intake",),
                endpoint_id=endpoint_id,
                at=now,
                mapping_id=mapping.mapping_id,
                external_actor_id=mapping.external_actor_id,
            )

        if not self.collaboration.actor_may_intake(
            tenant_id=event.tenant_id,
            actor_id=verified.actor_id,
            at=now,
        ):
            return self._record_non_origin(
                event=event,
                outcome=ProcessingOutcome.REJECTED,
                reason_codes=("reason.missing_authority",),
                endpoint_id=endpoint_id,
                at=now,
                mapping_id=mapping.mapping_id,
                external_actor_id=mapping.external_actor_id,
            )

        return self._accept_and_publish(
            event=event,
            mapping_id=mapping.mapping_id,
            external_actor_id=mapping.external_actor_id,
            actor_id=verified.actor_id,
            endpoint_id=endpoint_id,
            subject_text=intake.subject_text or "",
            at=now,
        )

    def _replay_or_repair_accepted(
        self,
        *,
        existing: InboundEventReceipt,
        event: NormalizedInboundEvent,
    ) -> IntakeHandleResult:
        origin = None
        if existing.task_origin_object_id is not None:
            origin = self.collaboration.get_task_origin(existing.task_origin_object_id)

        outbound_message = None
        outbound_ack = None
        outbox_item_id = None
        if (
            existing.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
            and origin is not None
        ):
            command_id = existing.command_id or self.id_factory()
            message = OutboundCollaborationMessage(
                message_id=self.id_factory(),
                tenant_id=event.tenant_id,
                provider=event.provider,
                destination=event.location,
                body_text=f"accepted: {origin.subject_text}",
                task_origin_object_id=origin.object_id,
                inbound_receipt_id=existing.receipt_id,
                command_id=command_id,
                idempotency_key=outbound_idempotency_key(
                    tenant_id=event.tenant_id,
                    provider=event.provider,
                    task_origin_object_id=origin.object_id,
                    status_kind="accepted",
                ),
                created_at=self.clock(),
            )
            enqueued = self.collaboration.enqueue_outbound_status(message)
            outbound_message = enqueued.message
            outbox_item_id = enqueued.outbox_item_id
            outbound_ack = self.adapter.publish_outbound(enqueued.message)

        return IntakeHandleResult(
            processing_outcome=ProcessingOutcome.DUPLICATE_REPLAY,
            verification_result=existing.verification_result,
            receipt=existing,
            origin=origin,
            outbound_message=outbound_message,
            outbound_ack=outbound_ack,
            outbox_item_id=outbox_item_id,
            created=False,
            reason_codes=("reason.duplicate_replay",),
        )

    def _record_non_origin(
        self,
        *,
        event: NormalizedInboundEvent,
        outcome: ProcessingOutcome,
        reason_codes: tuple[str, ...],
        endpoint_id: str | None,
        at: datetime,
        mapping_id: str | None = None,
        external_actor_id: str | None = None,
    ) -> IntakeHandleResult:
        self.collaboration.save_external_reference(event.source_reference)
        receipt = InboundEventReceipt(
            receipt_id=self.id_factory(),
            tenant_id=event.tenant_id,
            provider=event.provider,
            external_event_id=event.external_event_id,
            inbound_event_id=event.inbound_event_id,
            signed_source_reference_id=event.source_reference.reference_id,
            verification_result=event.verified_actor.verification_result,
            processing_outcome=outcome,
            reason_codes=reason_codes,
            checkpoint_token=self.id_factory(),
            created_at=at,
            mapping_id=mapping_id,
            external_actor_id=external_actor_id,
        )
        try:
            stored = self.collaboration.record_inbound_receipt(
                receipt, source_reference=event.source_reference, endpoint_id=endpoint_id
            )
        except (CrossTenantAccessError, MissingAuthorityError, MalformedCommandError):
            # Persist a rejected receipt without endpoint binding when endpoint
            # coupling fails; still prove absence of origin/outbox.
            stored = self.collaboration.record_inbound_receipt(
                receipt, source_reference=event.source_reference, endpoint_id=None
            )
        return IntakeHandleResult(
            processing_outcome=stored.processing_outcome,
            verification_result=stored.receipt.verification_result,
            receipt=stored.receipt,
            created=stored.created,
            reason_codes=stored.receipt.reason_codes,
        )

    def _accept_and_publish(
        self,
        *,
        event: NormalizedInboundEvent,
        mapping_id: str,
        external_actor_id: str,
        actor_id: str,
        endpoint_id: str,
        subject_text: str,
        at: datetime,
    ) -> IntakeHandleResult:
        origin_id = self.id_factory()
        receipt_id = self.id_factory()
        command_id = self.id_factory()
        receipt = InboundEventReceipt(
            receipt_id=receipt_id,
            tenant_id=event.tenant_id,
            provider=event.provider,
            external_event_id=event.external_event_id,
            inbound_event_id=event.inbound_event_id,
            signed_source_reference_id=event.source_reference.reference_id,
            verification_result=VerificationResult.VERIFIED,
            processing_outcome=ProcessingOutcome.ACCEPTED_ORIGIN,
            reason_codes=("reason.accepted_origin",),
            checkpoint_token=self.id_factory(),
            created_at=at,
            command_id=command_id,
            task_origin_object_id=origin_id,
            mapping_id=mapping_id,
            external_actor_id=external_actor_id,
        )
        origin = TaskOrigin(
            object_id=origin_id,
            tenant_id=event.tenant_id,
            actor_id=actor_id,
            inbound_receipt_id=receipt_id,
            source_reference_id=event.source_reference.reference_id,
            provider=event.provider,
            external_event_id=event.external_event_id,
            subject_text=subject_text,
            body_text=event.body_text,
            location_kind=event.location.location_kind,
            location_reference_id=event.location.external_location.reference_id,
            created_at=at,
            created_by_actor_id=self.created_by_actor_id,
            mapping_id=mapping_id,
            endpoint_id=endpoint_id,
            parent_location_reference_id=(
                None
                if event.location.parent_external_location is None
                else event.location.parent_external_location.reference_id
            ),
        )
        message = OutboundCollaborationMessage(
            message_id=self.id_factory(),
            tenant_id=event.tenant_id,
            provider=event.provider,
            destination=event.location,
            body_text=f"accepted: {subject_text}",
            task_origin_object_id=origin_id,
            inbound_receipt_id=receipt_id,
            command_id=command_id,
            idempotency_key=outbound_idempotency_key(
                tenant_id=event.tenant_id,
                provider=event.provider,
                task_origin_object_id=origin_id,
                status_kind="accepted",
            ),
            created_at=at,
        )
        accepted = self.collaboration.accept_task_origin_with_outbound(
            origin=origin,
            receipt=receipt,
            source_reference=event.source_reference,
            location_reference=event.location.external_location,
            parent_location_reference=event.location.parent_external_location,
            endpoint_id=endpoint_id,
            outbound=message,
        )
        ack = self.adapter.publish_outbound(accepted.message)
        return IntakeHandleResult(
            processing_outcome=(
                ProcessingOutcome.ACCEPTED_ORIGIN
                if accepted.created
                else ProcessingOutcome.DUPLICATE_REPLAY
            ),
            verification_result=VerificationResult.VERIFIED,
            receipt=accepted.receipt,
            origin=accepted.origin,
            outbound_message=accepted.message,
            outbound_ack=ack,
            outbox_item_id=accepted.outbox_item_id,
            created=accepted.created,
            reason_codes=(
                accepted.receipt.reason_codes
                if accepted.created
                else ("reason.duplicate_replay",)
            ),
        )
