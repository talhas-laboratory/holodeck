"""Policy bindings, precedence, and activation (M1-018 / GS-009)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.errors import GovernanceError, MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id


class PolicyUnauthorizedRelaxationError(GovernanceError):
    code = DomainErrorCode.POLICY_UNAUTHORIZED_RELAXATION


@dataclass(frozen=True, slots=True)
class PolicyBinding:
    binding_id: str
    tenant_id: str
    scope: str
    evaluator_id: str
    parameters: Mapping[str, str]
    created_at: datetime
    created_by_actor_id: str
    precedence: int
    effective_from: datetime
    effective_until: datetime | None = None
    schema_version: str = "m1.policy_binding.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("binding_id", self.binding_id),
            ("tenant_id", self.tenant_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        if self.scope not in {"tenant", "workspace", "object_exception"}:
            raise MalformedCommandError("invalid policy scope")
        if self.precedence < 1:
            raise MalformedCommandError("precedence must be >= 1")
        if self.created_at.tzinfo is None or self.effective_from.tzinfo is None:
            raise MalformedCommandError("timestamps must be timezone-aware UTC")


def merge_policy_parameters(
    higher: Mapping[str, str],
    lower: Mapping[str, str],
    *,
    allow_relaxation: bool = False,
) -> dict[str, str]:
    """Lower-precedence policy may only tighten unless relaxation is authorized."""

    merged = dict(higher)
    for key, value in lower.items():
        if key not in merged:
            merged[key] = value
            continue
        if value == merged[key]:
            continue
        # Numeric thresholds: for required_approvals, higher is tighter.
        if key == "required_approvals" or key.endswith("_min"):
            try:
                current = int(merged[key])
                proposed = int(value)
            except ValueError as exc:
                raise MalformedCommandError(f"non-numeric policy value for {key}") from exc
            if proposed < current and not allow_relaxation:
                raise PolicyUnauthorizedRelaxationError(
                    f"unauthorized relaxation of {key}"
                )
            merged[key] = str(proposed if allow_relaxation else max(current, proposed))
            continue
        if not allow_relaxation:
            raise PolicyUnauthorizedRelaxationError(f"unauthorized override of {key}")
        merged[key] = value
    return merged


def resolve_active_policy_parameters(
    bindings: Sequence[PolicyBinding],
    *,
    evaluator_id: str,
    at: datetime,
) -> dict[str, str]:
    params, _binding_ids = resolve_active_policy(
        bindings, evaluator_id=evaluator_id, at=at
    )
    return params


def resolve_active_policy(
    bindings: Sequence[PolicyBinding],
    *,
    evaluator_id: str,
    at: datetime,
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Merge effective bindings; return parameters and contributing binding ids."""

    active = [
        binding
        for binding in bindings
        if binding.evaluator_id == evaluator_id
        and binding.effective_from <= at
        and (binding.effective_until is None or binding.effective_until > at)
    ]
    active.sort(key=lambda binding: binding.precedence)
    merged: dict[str, str] = {}
    for binding in active:
        merged = merge_policy_parameters(
            merged,
            binding.parameters,
            allow_relaxation=binding.scope == "object_exception",
        )
    return merged, tuple(binding.binding_id for binding in active)
