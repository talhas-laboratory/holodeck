"""Immutable object revisions and current-head semantics."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from holodeck_governance.domain.errors import (
    MalformedCommandError,
    RevisionImmutableError,
    StaleRevisionError,
)
from holodeck_governance.domain.ids import require_opaque_id


@dataclass(frozen=True, slots=True)
class ObjectRevision:
    """One immutable revision of a governed object."""

    revision_id: str
    tenant_id: str
    object_id: str
    revision: int
    content_hash: str
    payload: Mapping[str, Any]
    created_at: datetime
    created_by_actor_id: str
    supersedes_revision: int | None = None
    finalized: bool = True
    schema_version: str = "m1.object_revision.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.revision_id, "revision_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.object_id, "object_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if self.revision < 1:
            raise MalformedCommandError("revision must be >= 1")
        if self.supersedes_revision is not None and self.supersedes_revision >= self.revision:
            raise MalformedCommandError("supersedes_revision must be less than revision")
        if not self.content_hash.strip():
            raise MalformedCommandError("content_hash is required")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class ObjectHead:
    object_id: str
    tenant_id: str
    head_revision: int
    head_revision_id: str


def content_hash_for(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def assert_revision_immutable(existing: ObjectRevision) -> None:
    if existing.finalized:
        raise RevisionImmutableError(
            f"revision {existing.object_id}@{existing.revision} is finalized and immutable"
        )


def assert_expected_head(*, head: ObjectHead, expected_revision: int) -> None:
    if head.head_revision != expected_revision:
        raise StaleRevisionError(
            f"expected revision {expected_revision} but head is {head.head_revision}"
        )
