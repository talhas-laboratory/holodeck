"""Durable workspace bindings for repositories and collaboration locations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from holodeck_governance.domain.collaboration.types import LocationKind
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc


class WorkspaceBindingStatus(StrEnum):
    """Lifecycle for workspace↔external bindings.

    Only ``active`` bindings participate in deterministic intake lookup.
    ``proposed`` supports genesis/review before activation; ``retired`` keeps
    history without resolving.
    """

    PROPOSED = "proposed"
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class RepositoryBinding:
    """Associates a repository/project with a Holodeck workspace.

    Preserves repository authority: the binding is not the repository and not
    the workspace.
    """

    binding_id: str
    tenant_id: str
    workspace_object_id: str
    provider: str
    external_repository_id: str
    canonical_locator: str
    default_branch: str
    status: WorkspaceBindingStatus
    external_reference_id: str
    created_at: datetime
    created_by_actor_id: str
    schema_version: str = "m2.repository_binding.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("binding_id", self.binding_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("external_reference_id", self.external_reference_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if not self.provider.strip():
            raise MalformedCommandError("provider is required")
        if not self.external_repository_id.strip():
            raise MalformedCommandError("external_repository_id is required")
        if not self.canonical_locator.strip():
            raise MalformedCommandError("canonical_locator is required")
        if not self.default_branch.strip():
            raise MalformedCommandError("default_branch is required")


@dataclass(frozen=True, slots=True)
class CollaborationLocationBinding:
    """Associates a collaboration location with a Holodeck workspace.

    Supports deterministic workspace selection for intake. The conversation
    location is never the system of record.
    """

    binding_id: str
    tenant_id: str
    workspace_object_id: str
    endpoint_id: str
    location_kind: LocationKind
    external_location_id: str
    location_reference_id: str
    status: WorkspaceBindingStatus
    created_at: datetime
    created_by_actor_id: str
    intake_policy_id: str | None = None
    schema_version: str = "m2.collaboration_location_binding.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("binding_id", self.binding_id),
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("endpoint_id", self.endpoint_id),
            ("location_reference_id", self.location_reference_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if not self.external_location_id.strip():
            raise MalformedCommandError("external_location_id is required")
        if self.intake_policy_id is not None:
            require_opaque_id(self.intake_policy_id, "intake_policy_id")


def repository_binding_dedupe_key(
    binding: RepositoryBinding,
) -> tuple[str, str, str]:
    return (binding.tenant_id, binding.provider, binding.external_repository_id)


def collaboration_location_binding_dedupe_key(
    binding: CollaborationLocationBinding,
) -> tuple[str, str, str, str]:
    return (
        binding.tenant_id,
        binding.endpoint_id,
        binding.location_kind.value,
        binding.external_location_id,
    )
