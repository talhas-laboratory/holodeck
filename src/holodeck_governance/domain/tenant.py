"""Tenant records and isolation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import CrossTenantAccessError, MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.metadata import GovernanceMetadata

DEFAULT_LOCAL_TENANT_SLUG = "local-default"
DEFAULT_LOCAL_TENANT_SCHEMA = "m1.tenant.v1"


@dataclass(frozen=True, slots=True)
class Tenant:
    """A tenant boundary for all governed records."""

    metadata: GovernanceMetadata
    slug: str
    display_name: str
    is_default_local: bool = False

    @property
    def id(self) -> str:
        return self.metadata.id

    def __post_init__(self) -> None:
        if not self.slug.strip():
            raise MalformedCommandError("tenant slug is required")
        if not self.display_name.strip():
            raise MalformedCommandError("tenant display_name is required")


def assert_same_tenant(*, actor_tenant_id: str, record_tenant_id: str, context: str) -> None:
    """Fail closed when a command crosses tenant boundaries."""

    left = require_opaque_id(actor_tenant_id, "actor_tenant_id")
    right = require_opaque_id(record_tenant_id, "record_tenant_id")
    if left != right:
        raise CrossTenantAccessError(
            f"cross-tenant access denied for {context}: actor={left} record={right}"
        )


def build_default_local_tenant(
    *,
    tenant_id: str,
    created_by_actor_id: str,
    created_at: datetime,
    provenance_ref: str | None = None,
) -> Tenant:
    metadata = GovernanceMetadata(
        id=tenant_id,
        tenant_id=tenant_id,
        schema_version=DEFAULT_LOCAL_TENANT_SCHEMA,
        created_at=created_at,
        created_by_actor_id=created_by_actor_id,
        provenance_ref=provenance_ref,
        status="active",
    )
    return Tenant(
        metadata=metadata,
        slug=DEFAULT_LOCAL_TENANT_SLUG,
        display_name="Local default tenant",
        is_default_local=True,
    )
