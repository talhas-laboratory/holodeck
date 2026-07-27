"""Shared governance metadata envelope contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.vocabulary import (
    REQUIRED_SHARED_METADATA_FIELDS,
    REVISIONED_METADATA_FIELDS,
)


@dataclass(frozen=True, slots=True)
class GovernanceMetadata:
    """Common fields required on every governed record."""

    id: str
    tenant_id: str
    schema_version: str
    created_at: datetime
    created_by_actor_id: str
    provenance_ref: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.id, "id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if not self.schema_version.strip():
            raise MalformedCommandError("schema_version is required")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class RevisionedMetadata:
    """Metadata for mutable conceptual objects with immutable revisions."""

    id: str
    tenant_id: str
    schema_version: str
    created_at: datetime
    created_by_actor_id: str
    object_id: str
    revision: int
    content_hash: str
    provenance_ref: str | None = None
    status: str | None = None
    supersedes_revision: int | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.id, "id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        require_opaque_id(self.object_id, "object_id")
        if not self.schema_version.strip():
            raise MalformedCommandError("schema_version is required")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")
        if self.revision < 1:
            raise MalformedCommandError("revision must be >= 1")
        if self.supersedes_revision is not None and self.supersedes_revision >= self.revision:
            raise MalformedCommandError("supersedes_revision must be less than revision")
        if not self.content_hash.strip():
            raise MalformedCommandError("content_hash is required")


def validate_shared_metadata_dict(payload: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_SHARED_METADATA_FIELDS if field not in payload]
    if missing:
        raise MalformedCommandError(f"missing shared metadata fields: {missing}")
    GovernanceMetadata(
        id=payload["id"],
        tenant_id=payload["tenant_id"],
        schema_version=payload["schema_version"],
        created_at=payload["created_at"],
        created_by_actor_id=payload["created_by_actor_id"],
        provenance_ref=payload.get("provenance_ref"),
        status=payload.get("status"),
    )


def validate_revisioned_metadata_dict(payload: dict[str, Any]) -> None:
    validate_shared_metadata_dict(payload)
    missing = [field for field in REVISIONED_METADATA_FIELDS if field not in payload]
    if missing:
        raise MalformedCommandError(f"missing revisioned metadata fields: {missing}")
    RevisionedMetadata(
        id=payload["id"],
        tenant_id=payload["tenant_id"],
        schema_version=payload["schema_version"],
        created_at=payload["created_at"],
        created_by_actor_id=payload["created_by_actor_id"],
        provenance_ref=payload.get("provenance_ref"),
        status=payload.get("status"),
        object_id=payload["object_id"],
        revision=payload["revision"],
        supersedes_revision=payload.get("supersedes_revision"),
        content_hash=payload["content_hash"],
    )
