"""Role assignments with jurisdiction and effective dating (M1-011)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    MalformedCommandError,
    MissingAuthorityError,
)
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.tenant import assert_same_tenant


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    assignment_id: str
    tenant_id: str
    actor_id: str
    role_object_id: str
    role_revision: int
    workspace_object_id: str | None
    jurisdiction_key: str
    jurisdiction_value: str
    effective_from: datetime
    created_at: datetime
    created_by_actor_id: str
    effective_until: datetime | None = None
    schema_version: str = "m1.role_assignment.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("assignment_id", self.assignment_id),
            ("tenant_id", self.tenant_id),
            ("actor_id", self.actor_id),
            ("role_object_id", self.role_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        if self.workspace_object_id is not None:
            require_opaque_id(self.workspace_object_id, "workspace_object_id")
        if self.role_revision < 1:
            raise MalformedCommandError("role_revision must be >= 1")
        if not self.jurisdiction_key.strip() or not self.jurisdiction_value.strip():
            raise MalformedCommandError("jurisdiction is required")
        for stamp in (self.effective_from, self.created_at, self.effective_until):
            if stamp is not None and stamp.tzinfo is None:
                raise MalformedCommandError("timestamps must be timezone-aware UTC")


def assignment_is_active(assignment: RoleAssignment, *, at: datetime) -> bool:
    if at < assignment.effective_from:
        return False
    if assignment.effective_until is not None and at >= assignment.effective_until:
        return False
    return True


def resolve_assignment(
    assignments: list[RoleAssignment],
    *,
    actor_id: str,
    tenant_id: str,
    jurisdiction_key: str,
    jurisdiction_value: str,
    at: datetime,
) -> RoleAssignment:
    matches: list[RoleAssignment] = []
    for item in assignments:
        assert_same_tenant(
            actor_tenant_id=tenant_id,
            record_tenant_id=item.tenant_id,
            context="role_assignment",
        )
        if item.actor_id != actor_id:
            continue
        if item.jurisdiction_key != jurisdiction_key:
            continue
        if item.jurisdiction_value != jurisdiction_value:
            continue
        if not assignment_is_active(item, at=at):
            continue
        matches.append(item)
    if not matches:
        raise MissingAuthorityError("no active in-scope role assignment")
    return sorted(matches, key=lambda item: item.effective_from, reverse=True)[0]


def reject_cross_tenant_assignment(assignment: RoleAssignment, actor_tenant_id: str) -> None:
    if assignment.tenant_id != actor_tenant_id:
        raise CrossTenantAccessError("role assignment cannot cross tenant boundary")
