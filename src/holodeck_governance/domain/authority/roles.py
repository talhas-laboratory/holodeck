"""Versioned role profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.revisions import content_hash_for


@dataclass(frozen=True, slots=True)
class RoleProfile:
    """Immutable role-profile revision (permissions + jurisdiction contract)."""

    role_profile_id: str
    tenant_id: str
    role_object_id: str
    revision: int
    name: str
    permissions: tuple[str, ...]
    jurisdiction: Mapping[str, str]
    created_at: datetime
    created_by_actor_id: str
    supersedes_revision: int | None = None
    content_hash: str = ""
    schema_version: str = "m1.role_profile.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.role_profile_id, "role_profile_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.role_object_id, "role_object_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if self.revision < 1:
            raise MalformedCommandError("revision must be >= 1")
        if not self.name.strip():
            raise MalformedCommandError("name is required")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


def role_profile_payload(role: RoleProfile) -> dict[str, object]:
    return {
        "name": role.name,
        "permissions": list(role.permissions),
        "jurisdiction": dict(role.jurisdiction),
    }


def with_content_hash(role: RoleProfile) -> RoleProfile:
    digest = content_hash_for(role_profile_payload(role))
    return RoleProfile(
        role_profile_id=role.role_profile_id,
        tenant_id=role.tenant_id,
        role_object_id=role.role_object_id,
        revision=role.revision,
        name=role.name,
        permissions=role.permissions,
        jurisdiction=dict(role.jurisdiction),
        created_at=role.created_at,
        created_by_actor_id=role.created_by_actor_id,
        supersedes_revision=role.supersedes_revision,
        content_hash=digest,
        schema_version=role.schema_version,
    )
