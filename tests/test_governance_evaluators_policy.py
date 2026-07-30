"""Tests for primitives, evaluation snapshots, and policy precedence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.errors import IncompleteEvaluationError
from holodeck_governance.domain.evaluation import (
    EvaluationResult,
    EvaluationSnapshot,
    reproduce_result,
)
from holodeck_governance.domain.evaluators.primitives import (
    Composition,
    PrimitiveOutcome,
    evaluate_composition,
    revision_matches_expected,
    transition_is_allowed,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.policy.binding import (
    PolicyBinding,
    PolicyUnauthorizedRelaxationError,
    merge_policy_parameters,
    resolve_active_policy_parameters,
)
from holodeck_governance.testing import FixtureIds


def test_primitives_and_composition() -> None:
    rev = revision_matches_expected({"expected_revision": 3, "actual_revision": 3})
    trans = transition_is_allowed({"transition_allowed": True})
    composed = evaluate_composition(
        Composition(op="all", primitives=("RevisionMatchesExpected", "TransitionIsAllowed")),
        (rev, trans),
    )
    assert composed.outcome is PrimitiveOutcome.PASS
    with pytest.raises(IncompleteEvaluationError):
        evaluate_composition(
            Composition(op="all", primitives=("RevisionMatchesExpected", "ActorHasPermission")),
            (rev,),
        )


def test_approval_and_grant_primitives() -> None:
    from holodeck_governance.domain.evaluators.primitives import (
        approval_applies_to_revision,
        grant_authorizes,
    )

    stale = approval_applies_to_revision(
        {"approval_subject_revision": 3, "subject_revision": 4}
    )
    assert stale.outcome is PrimitiveOutcome.FAIL
    assert stale.reason_code == ReasonCode.DENY_STALE_APPROVAL.value
    grant = grant_authorizes(
        {
            "grant_ok": False,
            "grant_deny_reason": ReasonCode.DENY_GRANT_REVOKED.value,
        }
    )
    assert grant.reason_code == ReasonCode.DENY_GRANT_REVOKED.value


def test_evaluation_snapshot_reproducible_gs008() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    snapshot = EvaluationSnapshot(
        snapshot_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        subject_object_id=ids.mission_object,
        subject_revision=3,
        input_refs={"policy": "binding-1", "role": "rev-2"},
        created_at=now,
    )
    result = EvaluationResult(
        result_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        snapshot_id=snapshot.snapshot_id,
        evaluator_contract_version="m1.PrepareTaskEvaluator.v1",
        outcome="allow",
        reason_codes=(ReasonCode.ALLOWED.value,),
        primitive_results=(),
        created_at=now,
    )
    assert reproduce_result(result) == result
    assert snapshot.input_refs["policy"] == "binding-1"


def test_policy_precedence_rejects_unauthorized_relaxation_gs009() -> None:
    tenant = {"required_approvals": "2"}
    workspace = {"required_approvals": "1"}
    with pytest.raises(PolicyUnauthorizedRelaxationError):
        merge_policy_parameters(tenant, workspace, allow_relaxation=False)
    tightened = merge_policy_parameters(tenant, {"required_approvals": "3"})
    assert tightened["required_approvals"] == "3"
    relaxed = merge_policy_parameters(tenant, workspace, allow_relaxation=True)
    assert relaxed["required_approvals"] == "1"


def test_resolve_active_policy_parameters_merges_by_precedence() -> None:
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    bindings = [
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            scope="tenant",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "1"},
            created_at=now,
            created_by_actor_id=ids.human_owner,
            precedence=10,
            effective_from=now,
        ),
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            scope="workspace",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "2"},
            created_at=now,
            created_by_actor_id=ids.human_owner,
            precedence=20,
            effective_from=now,
        ),
    ]
    merged = resolve_active_policy_parameters(
        bindings,
        evaluator_id="m1.TaskTransitionEvaluator.v1",
        at=now,
    )
    assert merged["required_approvals"] == "2"
