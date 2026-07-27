"""Durable task-origin records for explicit collaboration intake."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from holodeck_governance.domain.collaboration.types import (
    AdapterMetadata,
    LocationKind,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc


def _freeze_metadata(metadata: Mapping[str, str] | None) -> Mapping[str, str]:
    if metadata is None:
        return {}
    return {str(key): str(value) for key, value in metadata.items()}


@dataclass(frozen=True, slots=True)
class TaskOrigin:
    """Durable origin of governed work initiated from collaboration intake.

    A task origin is not a mission, run, approval, or acceptance decision.
    """

    object_id: str
    tenant_id: str
    actor_id: str
    inbound_receipt_id: str
    source_reference_id: str
    provider: str
    external_event_id: str
    subject_text: str
    body_text: str
    location_kind: LocationKind
    location_reference_id: str
    created_at: datetime
    created_by_actor_id: str
    endpoint_id: str | None = None
    parent_location_reference_id: str | None = None
    adapter_metadata: AdapterMetadata = field(default_factory=dict)
    schema_version: str = "m2.task_origin.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("object_id", self.object_id),
            ("tenant_id", self.tenant_id),
            ("actor_id", self.actor_id),
            ("inbound_receipt_id", self.inbound_receipt_id),
            ("source_reference_id", self.source_reference_id),
            ("location_reference_id", self.location_reference_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        if self.endpoint_id is not None:
            require_opaque_id(self.endpoint_id, "endpoint_id")
        if self.parent_location_reference_id is not None:
            require_opaque_id(
                self.parent_location_reference_id, "parent_location_reference_id"
            )
        require_utc(self.created_at, "created_at")
        if not self.provider.strip():
            raise MalformedCommandError("provider is required")
        if not self.external_event_id.strip():
            raise MalformedCommandError("external_event_id is required")
        if not self.subject_text.strip():
            raise MalformedCommandError("subject_text is required")
        if not self.body_text.strip():
            raise MalformedCommandError("body_text is required")
        object.__setattr__(self, "adapter_metadata", _freeze_metadata(self.adapter_metadata))


def task_origin_dedupe_key(origin: TaskOrigin) -> tuple[str, str, str]:
    return (origin.tenant_id, origin.provider, origin.external_event_id)
