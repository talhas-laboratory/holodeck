"""Evaluator and command reason-code catalog."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


CATALOG_VERSION: Final = "m1.reasons.v1"


class ReasonCode(StrEnum):
    """Stable reason codes returned by evaluators and command handling."""

    ALLOWED = "reason.allowed"
    DENY_TENANT_ISOLATION = "reason.deny.tenant_isolation"
    DENY_MISSING_AUTHORITY = "reason.deny.missing_authority"
    DENY_STALE_REVISION = "reason.deny.stale_revision"
    DENY_STALE_APPROVAL = "reason.deny.stale_approval"
    DENY_INVALID_TRANSITION = "reason.deny.invalid_transition"
    DENY_GRANT_EXPIRED = "reason.deny.grant_expired"
    DENY_GRANT_REVOKED = "reason.deny.grant_revoked"
    DENY_GRANT_WRONG_REVISION = "reason.deny.grant_wrong_revision"
    DENY_INCOMPLETE_INPUTS = "reason.deny.incomplete_inputs"
    DENY_POLICY_PRECEDENCE = "reason.deny.policy_precedence"
    DENY_MALFORMED_COMMAND = "reason.deny.malformed_command"
    DENY_IDEMPOTENCY_CONFLICT = "reason.deny.idempotency_conflict"
    DENY_REVISION_IMMUTABLE = "reason.deny.revision_immutable"
    DENY_EDGE_INVALID = "reason.deny.edge_invalid"
    REQUIRE_APPROVAL = "reason.require_approval"
    ESCALATE = "reason.escalate"
    LEGACY_IMPORT_ONLY = "reason.legacy_import_only"


@dataclass(frozen=True, slots=True)
class ReasonSpec:
    code: ReasonCode
    outcome_class: str
    summary: str


REASON_CODES: Final[dict[ReasonCode, ReasonSpec]] = {
    ReasonCode.ALLOWED: ReasonSpec(
        ReasonCode.ALLOWED, "allow", "Evaluator permitted the requested command."
    ),
    ReasonCode.DENY_TENANT_ISOLATION: ReasonSpec(
        ReasonCode.DENY_TENANT_ISOLATION,
        "deny",
        "Cross-tenant reference or mutation was rejected.",
    ),
    ReasonCode.DENY_MISSING_AUTHORITY: ReasonSpec(
        ReasonCode.DENY_MISSING_AUTHORITY,
        "deny",
        "No applicable role assignment or grant authorized the command.",
    ),
    ReasonCode.DENY_STALE_REVISION: ReasonSpec(
        ReasonCode.DENY_STALE_REVISION,
        "deny",
        "Expected revision did not match the current subject head.",
    ),
    ReasonCode.DENY_STALE_APPROVAL: ReasonSpec(
        ReasonCode.DENY_STALE_APPROVAL,
        "deny",
        "Approval applied to a superseded subject revision.",
    ),
    ReasonCode.DENY_INVALID_TRANSITION: ReasonSpec(
        ReasonCode.DENY_INVALID_TRANSITION,
        "deny",
        "Lifecycle definition disallows the requested transition.",
    ),
    ReasonCode.DENY_GRANT_EXPIRED: ReasonSpec(
        ReasonCode.DENY_GRANT_EXPIRED, "deny", "Referenced grant is expired."
    ),
    ReasonCode.DENY_GRANT_REVOKED: ReasonSpec(
        ReasonCode.DENY_GRANT_REVOKED, "deny", "Referenced grant is revoked."
    ),
    ReasonCode.DENY_GRANT_WRONG_REVISION: ReasonSpec(
        ReasonCode.DENY_GRANT_WRONG_REVISION,
        "deny",
        "Grant target revision does not match the command subject revision.",
    ),
    ReasonCode.DENY_INCOMPLETE_INPUTS: ReasonSpec(
        ReasonCode.DENY_INCOMPLETE_INPUTS,
        "deny",
        "Evaluation snapshot inputs were incomplete or unknown.",
    ),
    ReasonCode.DENY_POLICY_PRECEDENCE: ReasonSpec(
        ReasonCode.DENY_POLICY_PRECEDENCE,
        "deny",
        "Policy merge violated precedence or unauthorized relaxation rules.",
    ),
    ReasonCode.DENY_MALFORMED_COMMAND: ReasonSpec(
        ReasonCode.DENY_MALFORMED_COMMAND,
        "deny",
        "Command failed structural validation before evaluation.",
    ),
    ReasonCode.DENY_IDEMPOTENCY_CONFLICT: ReasonSpec(
        ReasonCode.DENY_IDEMPOTENCY_CONFLICT,
        "deny",
        "Idempotency key collision with differing semantics.",
    ),
    ReasonCode.DENY_REVISION_IMMUTABLE: ReasonSpec(
        ReasonCode.DENY_REVISION_IMMUTABLE,
        "deny",
        "Attempted in-place mutation of an immutable revision.",
    ),
    ReasonCode.DENY_EDGE_INVALID: ReasonSpec(
        ReasonCode.DENY_EDGE_INVALID,
        "deny",
        "Traceability edge failed existence, tenant, or type checks.",
    ),
    ReasonCode.REQUIRE_APPROVAL: ReasonSpec(
        ReasonCode.REQUIRE_APPROVAL,
        "require_approval",
        "Evaluator requires an exact-revision approval before transition.",
    ),
    ReasonCode.ESCALATE: ReasonSpec(
        ReasonCode.ESCALATE,
        "escalate",
        "Evaluator requires escalation before further progress.",
    ),
    ReasonCode.LEGACY_IMPORT_ONLY: ReasonSpec(
        ReasonCode.LEGACY_IMPORT_ONLY,
        "informational",
        "Record exists only as a legacy_import fact without M1 authority semantics.",
    ),
}
