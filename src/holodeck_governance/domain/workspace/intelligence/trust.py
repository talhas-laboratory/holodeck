"""Trust-class promotion rules for workspace intelligence sources."""

from __future__ import annotations

from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.workspace.intelligence.gaps import WorkspaceDecision
from holodeck_governance.domain.workspace.intelligence.sources import WorkspaceSource
from holodeck_governance.domain.workspace.intelligence.types import (
    TRUST_RANK,
    DecisionOutcome,
    TrustClass,
)


def trust_promotion_requires_human_decision(
    from_trust: TrustClass,
    to_trust: TrustClass,
) -> bool:
    """Return whether elevating from ``from_trust`` to ``to_trust`` needs a human decision.

    Untrusted references and generated interpretations may become instruction
    authority or authoritative reference only through an explicit approved human
    workspace decision. Any elevation into instruction authority likewise
    requires that decision. Lateral or downward changes never do.
    """

    if TRUST_RANK[to_trust] <= TRUST_RANK[from_trust]:
        return False
    if to_trust is TrustClass.INSTRUCTION_AUTHORITY:
        return True
    if (
        from_trust
        in {
            TrustClass.UNTRUSTED_REFERENCE,
            TrustClass.GENERATED_INTERPRETATION,
        }
        and to_trust
        in {
            TrustClass.AUTHORITATIVE_REFERENCE,
            TrustClass.INSTRUCTION_AUTHORITY,
        }
    ):
        return True
    return False


def assert_trust_promotion_allowed(
    *,
    from_trust: TrustClass,
    to_trust: TrustClass,
    decision_id: str | None,
) -> None:
    """Reject elevations that require a human decision without a decision_id.

    This is a shape check only: durable authorization is verified by loading the
    ``WorkspaceDecision`` and authorizing ``Actor`` at the application seam.
    """

    if not trust_promotion_requires_human_decision(from_trust, to_trust):
        return
    if decision_id is None:
        raise MalformedCommandError(
            "trust elevation requires an approved human workspace decision_id"
        )
    require_opaque_id(decision_id, "decision_id")


def assert_trust_promotion_decision_authorizes(
    *,
    decision: WorkspaceDecision,
    actor: Actor,
    source: WorkspaceSource,
) -> None:
    """Require an APPROVED HUMAN WorkspaceDecision bound to the source.

    Checks: actor is HUMAN and matches ``decision.authorized_actor_id``, same
    tenant/workspace as the source, outcome APPROVED, and
    ``subject_revision_id == source.source_id``.
    """

    if actor.kind is not ActorKind.HUMAN:
        raise MalformedCommandError(
            "trust promotion decision authorizing actor must be human"
        )
    if actor.actor_id != decision.authorized_actor_id:
        raise MalformedCommandError(
            "actor does not match trust promotion decision authorized_actor_id"
        )
    if actor.tenant_id != decision.tenant_id:
        raise MalformedCommandError("decision authorizing actor tenant mismatch")
    if decision.outcome is not DecisionOutcome.APPROVED:
        raise MalformedCommandError(
            "trust promotion requires an approved workspace decision"
        )
    if decision.subject_revision_id != source.source_id:
        raise MalformedCommandError(
            "trust promotion decision subject must be the source"
        )
    if decision.tenant_id != source.tenant_id:
        raise MalformedCommandError("trust promotion decision tenant mismatch")
    if decision.workspace_object_id != source.workspace_object_id:
        raise MalformedCommandError(
            "trust promotion decision workspace does not match source"
        )
