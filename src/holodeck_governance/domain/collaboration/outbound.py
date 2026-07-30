"""Outbound collaboration message contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.collaboration.inbound import ConversationLocation
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc


@dataclass(frozen=True, slots=True)
class OutboundCollaborationMessage:
    message_id: str
    tenant_id: str
    provider: str
    destination: ConversationLocation
    body_text: str
    task_origin_object_id: str
    inbound_receipt_id: str
    command_id: str
    idempotency_key: str
    created_at: datetime
    schema_version: str = "m2.outbound_collaboration_message.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("message_id", self.message_id),
            ("tenant_id", self.tenant_id),
            ("task_origin_object_id", self.task_origin_object_id),
            ("inbound_receipt_id", self.inbound_receipt_id),
            ("command_id", self.command_id),
        ):
            require_opaque_id(value, name)
        if not self.provider.strip():
            raise MalformedCommandError("provider is required")
        if not self.body_text.strip():
            raise MalformedCommandError("body_text is required")
        if not self.idempotency_key.strip():
            raise MalformedCommandError("idempotency_key is required")
        require_utc(self.created_at, "created_at")
        if self.destination.external_location.tenant_id != self.tenant_id:
            raise MalformedCommandError("destination tenant must match message tenant")


def outbound_idempotency_key(
    *,
    tenant_id: str,
    provider: str,
    task_origin_object_id: str,
    status_kind: str,
) -> str:
    """Stable semantic idempotency key for correlated status publication."""

    require_opaque_id(tenant_id, "tenant_id")
    require_opaque_id(task_origin_object_id, "task_origin_object_id")
    if not provider.strip() or not status_kind.strip():
        raise MalformedCommandError("provider and status_kind are required")
    return f"{tenant_id}:{provider}:status:{task_origin_object_id}:{status_kind}"
