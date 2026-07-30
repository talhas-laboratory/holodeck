"""Typed traceability edges (M1-009 / GS-005)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.errors import EdgeValidationError, MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.tenant import assert_same_tenant


# edge_type -> (from_type, to_type)
ALLOWED_EDGE_MATRIX: Final[dict[str, tuple[str, str]]] = {
    "supersedes": ("*", "*"),
    "mission_satisfies_intent": ("Mission", "Intent"),
    "task_belongs_to_mission": ("Task", "Mission"),
    "requirement_belongs_to_mission": ("Requirement", "Mission"),
    "evidence_supports_requirement": ("Evidence", "Requirement"),
    "approval_targets": ("Approval", "Mission"),
    "run_executes_task": ("Run", "Task"),
}


@dataclass(frozen=True, slots=True)
class TraceabilityEdge:
    edge_id: str
    tenant_id: str
    edge_type: str
    from_object_id: str
    from_revision: int
    to_object_id: str
    to_revision: int
    created_at: datetime
    created_by_actor_id: str
    provenance_ref: str | None = None
    validity_status: str = "active"
    schema_version: str = "m1.traceability_edge.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("edge_id", self.edge_id),
            ("tenant_id", self.tenant_id),
            ("from_object_id", self.from_object_id),
            ("to_object_id", self.to_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        if self.edge_type not in ALLOWED_EDGE_MATRIX:
            raise MalformedCommandError(f"unknown edge type: {self.edge_type}")
        if self.from_revision < 1 or self.to_revision < 1:
            raise MalformedCommandError("edge revisions must be >= 1")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


def validate_edge_endpoints(
    edge: TraceabilityEdge,
    *,
    from_object: GovernanceObject | None,
    to_object: GovernanceObject | None,
) -> None:
    if from_object is None or to_object is None:
        raise EdgeValidationError(
            "edge endpoint missing",
            code=DomainErrorCode.EDGE_ENDPOINT_MISSING,
        )
    assert_same_tenant(
        actor_tenant_id=edge.tenant_id,
        record_tenant_id=from_object.tenant_id,
        context="edge.from",
    )
    assert_same_tenant(
        actor_tenant_id=edge.tenant_id,
        record_tenant_id=to_object.tenant_id,
        context="edge.to",
    )
    expected = ALLOWED_EDGE_MATRIX[edge.edge_type]
    if expected[0] != "*" and from_object.object_type != expected[0]:
        raise EdgeValidationError(
            f"edge {edge.edge_type} incompatible from-type {from_object.object_type}",
            code=DomainErrorCode.EDGE_TYPE_INCOMPATIBLE,
        )
    if expected[1] != "*" and to_object.object_type != expected[1]:
        raise EdgeValidationError(
            f"edge {edge.edge_type} incompatible to-type {to_object.object_type}",
            code=DomainErrorCode.EDGE_TYPE_INCOMPATIBLE,
        )
