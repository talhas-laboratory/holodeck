"""Domain evaluation helpers used by command handling."""

from __future__ import annotations

from datetime import datetime

from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.errors import InvalidTransitionError
from holodeck_governance.domain.evaluation.snapshot import EvaluationResult, EvaluationSnapshot
from holodeck_governance.domain.evaluators.primitives import (
    Composition,
    PrimitiveOutcome,
    PrimitiveResult,
    actor_has_permission,
    approval_applies_to_revision,
    evaluate_composition,
    grant_authorizes,
    revision_matches_expected,
    transition_is_allowed,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.lifecycle import validate_task_transition


def evaluate_task_transition(
    *,
    tenant_id: str,
    subject_object_id: str,
    subject_revision: int | None,
    expected_revision: int | None,
    current_state: str,
    target_state: str,
    actor_permitted: bool,
    created_at: datetime,
    approval_subject_revision: int | None = None,
    grant_ok: bool | None = None,
    grant_deny_reason: str | None = None,
    policy_binding_id: str | None = None,
    selected_authority: dict[str, str] | None = None,
) -> tuple[EvaluationSnapshot, EvaluationResult, str | None]:
    """Return snapshot, result, and lifecycle definition version when allowed."""

    actual_revision = subject_revision
    snapshot = EvaluationSnapshot(
        snapshot_id=generate_uuidv7(),
        tenant_id=tenant_id,
        subject_object_id=subject_object_id,
        subject_revision=actual_revision or expected_revision or 1,
        input_refs={
            "current_state": current_state,
            "target_state": target_state,
            **(
                {"approval_subject_revision": str(approval_subject_revision)}
                if approval_subject_revision is not None
                else {}
            ),
        },
        created_at=created_at,
        policy_binding_id=policy_binding_id,
        authority_selection=selected_authority,
    )
    transition_allowed = True
    definition_version: str | None = None
    try:
        definition_version = validate_task_transition(current_state, target_state)
    except InvalidTransitionError:
        transition_allowed = False

    primitives: list[PrimitiveResult] = [
        revision_matches_expected(
            {
                "expected_revision": expected_revision,
                "actual_revision": (
                    actual_revision
                    if actual_revision is not None
                    else expected_revision
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
    if expected_revision is None and actual_revision is None:
        primitives[0] = PrimitiveResult(
            "RevisionMatchesExpected",
            PrimitiveOutcome.PASS,
            ReasonCode.ALLOWED.value,
        )
    if approval_subject_revision is not None:
        primitives.append(
            approval_applies_to_revision(
                {
                    "approval_subject_revision": approval_subject_revision,
                    "subject_revision": actual_revision or expected_revision,
                }
            )
        )
        composition_names.append("ApprovalAppliesToRevision")
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
        evaluator_contract_version="m1.TaskTransitionEvaluator.v1",
        outcome=outcome,
        reason_codes=reasons,
        primitive_results=tuple(primitives),
        created_at=created_at,
        policy_binding_id=policy_binding_id,
        evaluator_implementation_id="m1.TaskTransitionEvaluator.impl.v1",
        selected_authority=selected_authority,
    )
    return snapshot, result, definition_version if outcome == "allow" else None
