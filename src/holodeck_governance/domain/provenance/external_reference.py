"""Provider-neutral external references (M1-008)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id


@dataclass(frozen=True, slots=True)
class ExternalReference:
    reference_id: str
    tenant_id: str
    provider: str
    object_type: str
    external_object_id: str
    locator: str
    observed_at: datetime
    created_at: datetime
    created_by_actor_id: str
    subject_object_id: str | None = None
    content_hash: str | None = None
    schema_version: str = "m1.external_reference.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.reference_id, "reference_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if self.subject_object_id is not None:
            require_opaque_id(self.subject_object_id, "subject_object_id")
        for name, value in (
            ("provider", self.provider),
            ("object_type", self.object_type),
            ("external_object_id", self.external_object_id),
            ("locator", self.locator),
        ):
            if not value.strip():
                raise MalformedCommandError(f"{name} is required")
        if self.observed_at.tzinfo is None or self.created_at.tzinfo is None:
            raise MalformedCommandError("timestamps must be timezone-aware UTC")


def external_reference_dedupe_key(ref: ExternalReference) -> tuple[str, str, str, str]:
    """Tenant-scoped idempotency key; provider IDs never become kernel PKs."""

    return (ref.tenant_id, ref.provider, ref.object_type, ref.external_object_id)
