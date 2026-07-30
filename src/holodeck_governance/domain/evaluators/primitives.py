"""Typed governance primitives and composition (M1-016)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Final, Mapping, Sequence

from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.errors import IncompleteEvaluationError, MalformedCommandError


class PrimitiveOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PrimitiveResult:
    primitive_id: str
    outcome: PrimitiveOutcome
    reason_code: str
    details: Mapping[str, str] | None = None


PrimitiveFn = Callable[[Mapping[str, object]], PrimitiveResult]


def revision_matches_expected(inputs: Mapping[str, object]) -> PrimitiveResult:
    expected = inputs.get("expected_revision")
    actual = inputs.get("actual_revision")
    if expected is None or actual is None:
        return PrimitiveResult(
            "RevisionMatchesExpected",
            PrimitiveOutcome.UNKNOWN,
            ReasonCode.DENY_INCOMPLETE_INPUTS.value,
        )
    if expected == actual:
        return PrimitiveResult(
            "RevisionMatchesExpected",
            PrimitiveOutcome.PASS,
            ReasonCode.ALLOWED.value,
        )
    return PrimitiveResult(
        "RevisionMatchesExpected",
        PrimitiveOutcome.FAIL,
        ReasonCode.DENY_STALE_REVISION.value,
    )


def transition_is_allowed(inputs: Mapping[str, object]) -> PrimitiveResult:
    allowed = inputs.get("transition_allowed")
    if allowed is None:
        return PrimitiveResult(
            "TransitionIsAllowed",
            PrimitiveOutcome.UNKNOWN,
            ReasonCode.DENY_INCOMPLETE_INPUTS.value,
        )
    if allowed:
        return PrimitiveResult(
            "TransitionIsAllowed",
            PrimitiveOutcome.PASS,
            ReasonCode.ALLOWED.value,
        )
    return PrimitiveResult(
        "TransitionIsAllowed",
        PrimitiveOutcome.FAIL,
        ReasonCode.DENY_INVALID_TRANSITION.value,
    )


def actor_has_permission(inputs: Mapping[str, object]) -> PrimitiveResult:
    permitted = inputs.get("actor_permitted")
    if permitted is None:
        return PrimitiveResult(
            "ActorHasPermission",
            PrimitiveOutcome.UNKNOWN,
            ReasonCode.DENY_INCOMPLETE_INPUTS.value,
        )
    if permitted:
        return PrimitiveResult(
            "ActorHasPermission",
            PrimitiveOutcome.PASS,
            ReasonCode.ALLOWED.value,
        )
    return PrimitiveResult(
        "ActorHasPermission",
        PrimitiveOutcome.FAIL,
        ReasonCode.DENY_MISSING_AUTHORITY.value,
    )


def approval_applies_to_revision(inputs: Mapping[str, object]) -> PrimitiveResult:
    approval_revision = inputs.get("approval_subject_revision")
    subject_revision = inputs.get("subject_revision")
    if approval_revision is None or subject_revision is None:
        return PrimitiveResult(
            "ApprovalAppliesToRevision",
            PrimitiveOutcome.UNKNOWN,
            ReasonCode.DENY_INCOMPLETE_INPUTS.value,
        )
    if approval_revision == subject_revision:
        return PrimitiveResult(
            "ApprovalAppliesToRevision",
            PrimitiveOutcome.PASS,
            ReasonCode.ALLOWED.value,
        )
    return PrimitiveResult(
        "ApprovalAppliesToRevision",
        PrimitiveOutcome.FAIL,
        ReasonCode.DENY_STALE_APPROVAL.value,
    )


def grant_authorizes(inputs: Mapping[str, object]) -> PrimitiveResult:
    ok = inputs.get("grant_ok")
    if ok is None:
        return PrimitiveResult(
            "GrantAuthorizes",
            PrimitiveOutcome.UNKNOWN,
            ReasonCode.DENY_INCOMPLETE_INPUTS.value,
        )
    if ok:
        return PrimitiveResult(
            "GrantAuthorizes",
            PrimitiveOutcome.PASS,
            ReasonCode.ALLOWED.value,
        )
    reason = str(inputs.get("grant_deny_reason") or ReasonCode.DENY_MISSING_AUTHORITY.value)
    return PrimitiveResult(
        "GrantAuthorizes",
        PrimitiveOutcome.FAIL,
        reason,
    )


PRIMITIVE_REGISTRY: Final[dict[str, PrimitiveFn]] = {
    "RevisionMatchesExpected": revision_matches_expected,
    "TransitionIsAllowed": transition_is_allowed,
    "ActorHasPermission": actor_has_permission,
    "ApprovalAppliesToRevision": approval_applies_to_revision,
    "GrantAuthorizes": grant_authorizes,
}

COMPOSITION_OPS: Final[frozenset[str]] = frozenset({"all", "any", "at_least"})


@dataclass(frozen=True, slots=True)
class Composition:
    op: str
    primitives: tuple[str, ...]
    threshold: int | None = None

    def __post_init__(self) -> None:
        if self.op not in COMPOSITION_OPS:
            raise MalformedCommandError(f"unsupported composition op: {self.op}")
        if self.op == "at_least" and (self.threshold is None or self.threshold < 1):
            raise MalformedCommandError("at_least requires threshold >= 1")
        if not self.primitives:
            raise MalformedCommandError("composition requires primitives")


def evaluate_composition(
    composition: Composition,
    results: Sequence[PrimitiveResult],
) -> PrimitiveResult:
    by_id = {item.primitive_id: item for item in results}
    selected = []
    for name in composition.primitives:
        if name not in by_id:
            raise IncompleteEvaluationError(f"missing primitive result: {name}")
        selected.append(by_id[name])
    if any(item.outcome is PrimitiveOutcome.UNKNOWN for item in selected):
        raise IncompleteEvaluationError("unknown primitive input; fail closed")
    passes = [item for item in selected if item.outcome is PrimitiveOutcome.PASS]
    if composition.op == "all":
        ok = len(passes) == len(selected)
    elif composition.op == "any":
        ok = bool(passes)
    else:
        ok = len(passes) >= int(composition.threshold or 0)
    return PrimitiveResult(
        f"composition:{composition.op}",
        PrimitiveOutcome.PASS if ok else PrimitiveOutcome.FAIL,
        ReasonCode.ALLOWED.value if ok else ReasonCode.DENY_MISSING_AUTHORITY.value,
    )
