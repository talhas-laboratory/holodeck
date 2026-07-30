"""Domain evaluation helpers for run transitions."""

from __future__ import annotations

from datetime import datetime

from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.errors import InvalidTransitionError
from holodeck_governance.domain.evaluation.snapshot import EvaluationResult, EvaluationSnapshot
from holodeck_governance.domain.evaluators.primitives import (
    Composition,
    PrimitiveOutcome,
    actor_has_permission,
    evaluate_composition,
    grant_authorizes,
    revision_matches_expected,
    transition_is_allowed,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.lifecycle import validate_run_transition


def evaluate_run_transition(
    *,
    tenant_id: str,
    subject_object_id: str,
    subject_revision: int | None,
    expected_revision: int | None,
    current_state: str,
    target_state: str,
    actor_permitted: bool,
    created_at: datetime,
    grant_ok: bool | None = None,
    grant_deny_reason: str | None = None,
) -> tuple[EvaluationSnapshot, EvaluationResult, str | None]:
    actual_revision = subject_revision
    snapshot = EvaluationSnapshot(
        snapshot_id=generate_uuidv7(),
        tenant_id=tenant_id,
        subject_object_id=subject_object_id,
        subject_revision=actual_revision or expected_revision or 1,
        input_refs={
            "current_state": current_state,
            "target_state": target_state,
            "subject_kind": "Run",
        },
        created_at=created_at,
    )
    transition_allowed = True
    definition_version: str | None = None
    try:
        definition_version = validate_run_transition(current_state, target_state)
    except InvalidTransitionError:
        transition_allowed = False

    primitives = [
        revision_matches_expected(
            {
                "expected_revision": expected_revision,
                "actual_revision": (
                    actual_revision if actual_revision is not None else expected_revision
                ),
            }
        ),
        transition_is_allowed({"transition_allowed": transition_allowed}),
        actor_has_permission({"actor_permitted": actor_permitted}),
    ]
    composition_names = [
        "RevisionMatchesExpected",
        "TransitionIsAllowed",
        "ActorHasPermission",
    ]
    if grant_ok is not None:
        primitives.append(
            grant_authorizes(
                {
                    "grant_ok": grant_ok,
                    "grant_deny_reason": grant_deny_reason
                    or ReasonCode.DENY_MISSING_AUTHORITY.value,
                }
            )
        )
        composition_names.append("GrantAuthorizes")

    composed = evaluate_composition(
        Composition(op="all", primitives=tuple(composition_names)),
        primitives,
    )
    if composed.outcome is PrimitiveOutcome.PASS:
        outcome = "allow"
        reasons = (ReasonCode.ALLOWED.value,)
    else:
        outcome = "deny"
        reasons = tuple(
            item.reason_code
            for item in primitives
            if item.outcome is not PrimitiveOutcome.PASS
        ) or (ReasonCode.DENY_MISSING_AUTHORITY.value,)

    result = EvaluationResult(
        result_id=generate_uuidv7(),
        tenant_id=tenant_id,
        snapshot_id=snapshot.snapshot_id,
        evaluator_contract_version="m1.RunTransitionEvaluator.v1",
        outcome=outcome,
        reason_codes=reasons,
        primitive_results=tuple(primitives),
        created_at=created_at,
        evaluator_implementation_id="m1.RunTransitionEvaluator.impl.v1",
    )
    return snapshot, result, definition_version if outcome == "allow" else None
