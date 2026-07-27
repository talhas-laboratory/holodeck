"""Evaluation snapshots and results (M1-017 / GS-008)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.evaluators.primitives import PrimitiveResult
from holodeck_governance.domain.ids import require_opaque_id


@dataclass(frozen=True, slots=True)
class EvaluationSnapshot:
    snapshot_id: str
    tenant_id: str
    subject_object_id: str
    subject_revision: int
    input_refs: Mapping[str, str]
    created_at: datetime
    policy_binding_id: str | None = None
    authority_selection: Mapping[str, str] | None = None
    schema_version: str = "m1.evaluation_snapshot.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.snapshot_id, "snapshot_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.subject_object_id, "subject_object_id")
        if self.subject_revision < 1:
            raise MalformedCommandError("subject_revision must be >= 1")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    result_id: str
    tenant_id: str
    snapshot_id: str
    evaluator_contract_version: str
    outcome: str
    reason_codes: tuple[str, ...]
    primitive_results: tuple[PrimitiveResult, ...]
    created_at: datetime
    policy_binding_id: str | None = None
    evaluator_implementation_id: str = "m1.TaskTransitionEvaluator.impl.v1"
    selected_authority: Mapping[str, str] | None = None
    schema_version: str = "m1.evaluation_result.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.result_id, "result_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.snapshot_id, "snapshot_id")
        if self.outcome not in {"allow", "deny", "require_approval", "escalate"}:
            raise MalformedCommandError("invalid evaluation outcome")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


def reproduce_result(stored: EvaluationResult) -> EvaluationResult:
    """Snapshots are immutable; reproduction returns the same structured result."""

    return stored
