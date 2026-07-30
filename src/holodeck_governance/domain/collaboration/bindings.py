"""Durable collaboration endpoint and external-actor mapping records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Mapping

from holodeck_governance.domain.collaboration.types import AdapterMetadata
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc


class BindingStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


def _freeze_metadata(metadata: Mapping[str, str] | None) -> Mapping[str, str]:
    if metadata is None:
        return {}
    return {str(key): str(value) for key, value in metadata.items()}


@dataclass(frozen=True, slots=True)
class CollaborationEndpoint:
    """Tenant-scoped collaboration provider endpoint.

    An endpoint identifies where Holodeck listens or publishes for one provider
    community/host binding. It is not a workspace and not a chat channel alone.
    """

    endpoint_id: str
    tenant_id: str
    provider: str
    external_endpoint_id: str
    locator: str
    status: BindingStatus
    created_at: datetime
    created_by_actor_id: str
    display_name: str = ""
    adapter_metadata: AdapterMetadata = field(default_factory=dict)
    schema_version: str = "m2.collaboration_endpoint.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.endpoint_id, "endpoint_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        require_utc(self.created_at, "created_at")
        if not self.provider.strip():
            raise MalformedCommandError("provider is required")
        if not self.external_endpoint_id.strip():
            raise MalformedCommandError("external_endpoint_id is required")
        if not self.locator.strip():
            raise MalformedCommandError("locator is required")
        object.__setattr__(self, "adapter_metadata", _freeze_metadata(self.adapter_metadata))


@dataclass(frozen=True, slots=True)
class ExternalActorMapping:
    """Maps a verified external identity onto a Holodeck actor within a tenant."""

    mapping_id: str
    tenant_id: str
    endpoint_id: str
    actor_id: str
    external_identity_reference_id: str
    status: BindingStatus
    created_at: datetime
    created_by_actor_id: str
    provider: str
    external_actor_id: str
    adapter_metadata: AdapterMetadata = field(default_factory=dict)
    schema_version: str = "m2.external_actor_mapping.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("mapping_id", self.mapping_id),
            ("tenant_id", self.tenant_id),
            ("endpoint_id", self.endpoint_id),
            ("actor_id", self.actor_id),
            ("external_identity_reference_id", self.external_identity_reference_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if not self.provider.strip() or not self.external_actor_id.strip():
            raise MalformedCommandError("provider and external_actor_id are required")
        object.__setattr__(self, "adapter_metadata", _freeze_metadata(self.adapter_metadata))


def endpoint_dedupe_key(endpoint: CollaborationEndpoint) -> tuple[str, str, str]:
    return (endpoint.tenant_id, endpoint.provider, endpoint.external_endpoint_id)


def actor_mapping_dedupe_key(mapping: ExternalActorMapping) -> tuple[str, str, str]:
    return (mapping.tenant_id, mapping.provider, mapping.external_actor_id)
