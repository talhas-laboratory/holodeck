"""Command envelope type."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.revisions import content_hash_for


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    command_id: str
    command_type: str
    tenant_id: str
    actor_id: str
    target_object_id: str
    expected_revision: int | None
    idempotency_key: str
    payload_schema_version: str
    correlation_id: str
    issued_at: datetime
    payload: Mapping[str, Any]
    role_assignment_id: str | None = None
    grant_id: str | None = None
    schema_version: str = "m1.command.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("command_id", self.command_id),
            ("tenant_id", self.tenant_id),
            ("actor_id", self.actor_id),
            ("target_object_id", self.target_object_id),
            ("correlation_id", self.correlation_id),
        ):
            require_opaque_id(value, name)
        if not self.command_type.strip() or not self.idempotency_key.strip():
            raise MalformedCommandError("command_type and idempotency_key required")
        if self.expected_revision is not None and self.expected_revision < 1:
            raise MalformedCommandError("expected_revision must be >= 1")
        if self.issued_at.tzinfo is None:
            raise MalformedCommandError("issued_at must be timezone-aware UTC")


def semantic_fingerprint(command: CommandEnvelope) -> str:
    return content_hash_for(
        {
            "command_type": command.command_type,
            "tenant_id": command.tenant_id,
            "actor_id": command.actor_id,
            "target_object_id": command.target_object_id,
            "expected_revision": command.expected_revision,
            "payload_schema_version": command.payload_schema_version,
            "payload": dict(command.payload),
            "role_assignment_id": command.role_assignment_id,
            "grant_id": command.grant_id,
        }
    )
