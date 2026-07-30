"""Normalized inbound collaboration contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from holodeck_governance.domain.collaboration.types import (
    AdapterMetadata,
    LocationKind,
    VerificationResult,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.records._common import require_utc


def _freeze_metadata(metadata: Mapping[str, str] | None) -> Mapping[str, str]:
    if metadata is None:
        return {}
    frozen = {str(key): str(value) for key, value in metadata.items()}
    return frozen


@dataclass(frozen=True, slots=True)
class VerifiedActorIdentity:
    tenant_id: str
    actor_id: str
    external_identity: ExternalReference
    verification_result: VerificationResult
    verified_at: datetime
    adapter_metadata: AdapterMetadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.actor_id, "actor_id")
        require_utc(self.verified_at, "verified_at")
        if self.external_identity.tenant_id != self.tenant_id:
            raise MalformedCommandError(
                "verified actor external identity tenant must match actor tenant"
            )
        object.__setattr__(self, "adapter_metadata", _freeze_metadata(self.adapter_metadata))


@dataclass(frozen=True, slots=True)
class ConversationLocation:
    location_kind: LocationKind
    external_location: ExternalReference
    parent_external_location: ExternalReference | None = None
    endpoint_id: str | None = None
    adapter_metadata: AdapterMetadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.endpoint_id is not None:
            require_opaque_id(self.endpoint_id, "endpoint_id")
        if (
            self.parent_external_location is not None
            and self.parent_external_location.tenant_id
            != self.external_location.tenant_id
        ):
            raise MalformedCommandError(
                "parent location tenant must match location tenant"
            )
        object.__setattr__(self, "adapter_metadata", _freeze_metadata(self.adapter_metadata))


@dataclass(frozen=True, slots=True)
class AttachmentRef:
    attachment_id: str
    external_attachment: ExternalReference
    content_type: str
    content_hash: str | None = None
    byte_size: int | None = None
    adapter_metadata: AdapterMetadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_opaque_id(self.attachment_id, "attachment_id")
        if not self.content_type.strip():
            raise MalformedCommandError("content_type is required")
        if self.byte_size is not None and self.byte_size < 0:
            raise MalformedCommandError("byte_size must be >= 0")
        object.__setattr__(self, "adapter_metadata", _freeze_metadata(self.adapter_metadata))


@dataclass(frozen=True, slots=True)
class NormalizedInboundEvent:
    inbound_event_id: str
    tenant_id: str
    provider: str
    external_event_id: str
    occurred_at: datetime
    received_at: datetime
    verified_actor: VerifiedActorIdentity
    location: ConversationLocation
    body_text: str
    source_reference: ExternalReference
    attachments: tuple[AttachmentRef, ...] = ()
    adapter_metadata: AdapterMetadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_opaque_id(self.inbound_event_id, "inbound_event_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_utc(self.occurred_at, "occurred_at")
        require_utc(self.received_at, "received_at")
        if not self.provider.strip():
            raise MalformedCommandError("provider is required")
        if not self.external_event_id.strip():
            raise MalformedCommandError("external_event_id is required")
        if self.verified_actor.tenant_id != self.tenant_id:
            raise MalformedCommandError("verified actor tenant must match event tenant")
        if self.source_reference.tenant_id != self.tenant_id:
            raise MalformedCommandError("source reference tenant must match event tenant")
        if self.location.external_location.tenant_id != self.tenant_id:
            raise MalformedCommandError("location tenant must match event tenant")
        object.__setattr__(self, "adapter_metadata", _freeze_metadata(self.adapter_metadata))
