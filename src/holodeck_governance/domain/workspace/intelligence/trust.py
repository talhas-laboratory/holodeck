"""Trust-class promotion rules for workspace intelligence sources."""

from __future__ import annotations

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.workspace.intelligence.types import TRUST_RANK, TrustClass


def assert_trust_promotion_allowed(
    *,
    from_trust: TrustClass,
    to_trust: TrustClass,
    authorized_human_promotion: bool,
) -> None:
    """Reject silent escalation into instruction authority.

    Untrusted references and generated interpretations may become instruction
    authority only through an explicit authorized human promotion. Lateral or
    downward changes are always allowed.
    """

    if TRUST_RANK[to_trust] <= TRUST_RANK[from_trust]:
        return
    if to_trust is TrustClass.INSTRUCTION_AUTHORITY and not authorized_human_promotion:
        raise MalformedCommandError(
            "instruction_authority requires explicit authorized human promotion"
        )
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
        and not authorized_human_promotion
    ):
        raise MalformedCommandError(
            "promoting untrusted or generated content requires authorized human promotion"
        )
