"""Inbound event receipts and checkpoint tokens."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.collaboration.types import (
    ProcessingOutcome,
    VerificationResult,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc


@dataclass(frozen=True, slots=True)
class InboundEventReceipt:
    receipt_id: str
    tenant_id: str
    provider: str
    external_event_id: str
    inbound_event_id: str
    signed_source_reference_id: str
    verification_result: VerificationResult
    processing_outcome: ProcessingOutcome
    reason_codes: tuple[str, ...]
    checkpoint_token: str
    created_at: datetime
    command_id: str | None = None
    task_origin_object_id: str | None = None
    mapping_id: str | None = None
    external_actor_id: str | None = None
    schema_version: str = "m2.inbound_event_receipt.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("receipt_id", self.receipt_id),
            ("tenant_id", self.tenant_id),
            ("inbound_event_id", self.inbound_event_id),
            ("signed_source_reference_id", self.signed_source_reference_id),
            ("checkpoint_token", self.checkpoint_token),
        ):
            require_opaque_id(value, name)
        if not self.provider.strip() or not self.external_event_id.strip():
            raise MalformedCommandError("provider and external_event_id are required")
        require_utc(self.created_at, "created_at")
        if self.command_id is not None:
            require_opaque_id(self.command_id, "command_id")
        if self.task_origin_object_id is not None:
            require_opaque_id(self.task_origin_object_id, "task_origin_object_id")
        if self.mapping_id is not None:
            require_opaque_id(self.mapping_id, "mapping_id")
        if self.external_actor_id is not None and not self.external_actor_id.strip():
            raise MalformedCommandError("external_actor_id must be non-empty when set")
        if (
            self.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
            and self.task_origin_object_id is None
        ):
            raise MalformedCommandError(
                "accepted_origin receipts require task_origin_object_id"
            )
        if (
            self.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
            and self.mapping_id is None
        ):
            raise MalformedCommandError(
                "accepted_origin receipts require mapping_id"
            )
        if (
            self.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
            and (self.external_actor_id is None or not self.external_actor_id.strip())
        ):
            raise MalformedCommandError(
                "accepted_origin receipts require external_actor_id"
            )
        if (
            self.processing_outcome is not ProcessingOutcome.ACCEPTED_ORIGIN
            and self.task_origin_object_id is not None
        ):
            raise MalformedCommandError(
                "task_origin_object_id is only valid for accepted_origin"
            )


def inbound_receipt_dedupe_key(
    receipt: InboundEventReceipt,
) -> tuple[str, str, str]:
    """Uniqueness constraint for durable inbound receipts."""

    return (receipt.tenant_id, receipt.provider, receipt.external_event_id)
