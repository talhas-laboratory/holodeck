"""Domain error catalog.

Adapters may map transport failures onto these codes. Tests and command
receipts must assert catalog identifiers, not prose-only messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


CATALOG_VERSION: Final = "m1.errors.v1"


class DomainErrorCode(StrEnum):
    """Stable domain-error identifiers for M1."""

    INVALID_TRANSITION = "err.invalid_transition"
    STALE_REVISION = "err.stale_revision"
    MISSING_AUTHORITY = "err.missing_authority"
    CROSS_TENANT_ACCESS = "err.cross_tenant_access"
    MALFORMED_COMMAND = "err.malformed_command"
    IDEMPOTENCY_CONFLICT = "err.idempotency_conflict"
    INCOMPLETE_EVALUATION = "err.incomplete_evaluation"
    REVISION_IMMUTABLE = "err.revision_immutable"
    EDGE_ENDPOINT_MISSING = "err.edge_endpoint_missing"
    EDGE_TYPE_INCOMPATIBLE = "err.edge_type_incompatible"
    GRANT_EXPIRED = "err.grant_expired"
    GRANT_REVOKED = "err.grant_revoked"
    GRANT_WRONG_REVISION = "err.grant_wrong_revision"
    POLICY_UNAUTHORIZED_RELAXATION = "err.policy_unauthorized_relaxation"
    NOT_FOUND = "err.not_found"
    UNSUPPORTED_LEGACY_MAPPING = "err.unsupported_legacy_mapping"
    CONTENTION = "err.contention"
    INTERNAL = "err.internal"


@dataclass(frozen=True, slots=True)
class DomainErrorSpec:
    code: DomainErrorCode
    category: str
    summary: str
    retryable: bool = False


DOMAIN_ERRORS: Final[dict[DomainErrorCode, DomainErrorSpec]] = {
    DomainErrorCode.INVALID_TRANSITION: DomainErrorSpec(
        DomainErrorCode.INVALID_TRANSITION,
        "lifecycle",
        "Requested subject transition is not allowed for the active definition version.",
    ),
    DomainErrorCode.STALE_REVISION: DomainErrorSpec(
        DomainErrorCode.STALE_REVISION,
        "revision",
        "Command or authority input targets a superseded or unexpected revision.",
    ),
    DomainErrorCode.MISSING_AUTHORITY: DomainErrorSpec(
        DomainErrorCode.MISSING_AUTHORITY,
        "authority",
        "Actor lacks an applicable role assignment or delegated grant.",
    ),
    DomainErrorCode.CROSS_TENANT_ACCESS: DomainErrorSpec(
        DomainErrorCode.CROSS_TENANT_ACCESS,
        "tenancy",
        "Command attempted to reference or mutate a record outside the actor tenant.",
    ),
    DomainErrorCode.MALFORMED_COMMAND: DomainErrorSpec(
        DomainErrorCode.MALFORMED_COMMAND,
        "command",
        "Command envelope or payload failed schema or invariant validation.",
    ),
    DomainErrorCode.IDEMPOTENCY_CONFLICT: DomainErrorSpec(
        DomainErrorCode.IDEMPOTENCY_CONFLICT,
        "command",
        "Idempotency key reused with a different semantic payload.",
    ),
    DomainErrorCode.INCOMPLETE_EVALUATION: DomainErrorSpec(
        DomainErrorCode.INCOMPLETE_EVALUATION,
        "evaluation",
        "Evaluation inputs are missing, unknown, or stale; fail closed.",
    ),
    DomainErrorCode.REVISION_IMMUTABLE: DomainErrorSpec(
        DomainErrorCode.REVISION_IMMUTABLE,
        "revision",
        "Finalized revision content cannot be mutated in place.",
    ),
    DomainErrorCode.EDGE_ENDPOINT_MISSING: DomainErrorSpec(
        DomainErrorCode.EDGE_ENDPOINT_MISSING,
        "graph",
        "Traceability edge references a missing governance object endpoint.",
    ),
    DomainErrorCode.EDGE_TYPE_INCOMPATIBLE: DomainErrorSpec(
        DomainErrorCode.EDGE_TYPE_INCOMPATIBLE,
        "graph",
        "Edge type is incompatible with endpoint object types.",
    ),
    DomainErrorCode.GRANT_EXPIRED: DomainErrorSpec(
        DomainErrorCode.GRANT_EXPIRED,
        "authority",
        "Delegated grant is past its expiry.",
    ),
    DomainErrorCode.GRANT_REVOKED: DomainErrorSpec(
        DomainErrorCode.GRANT_REVOKED,
        "authority",
        "Delegated grant has been revoked.",
    ),
    DomainErrorCode.GRANT_WRONG_REVISION: DomainErrorSpec(
        DomainErrorCode.GRANT_WRONG_REVISION,
        "authority",
        "Delegated grant targets a different subject revision than requested.",
    ),
    DomainErrorCode.POLICY_UNAUTHORIZED_RELAXATION: DomainErrorSpec(
        DomainErrorCode.POLICY_UNAUTHORIZED_RELAXATION,
        "policy",
        "Lower-precedence policy attempted an unauthorized relaxation.",
    ),
    DomainErrorCode.NOT_FOUND: DomainErrorSpec(
        DomainErrorCode.NOT_FOUND,
        "lookup",
        "Requested governed record does not exist in the tenant scope.",
    ),
    DomainErrorCode.UNSUPPORTED_LEGACY_MAPPING: DomainErrorSpec(
        DomainErrorCode.UNSUPPORTED_LEGACY_MAPPING,
        "migration",
        "Legacy value has an explicit unsupported disposition for M1 import.",
    ),
    DomainErrorCode.CONTENTION: DomainErrorSpec(
        DomainErrorCode.CONTENTION,
        "concurrency",
        "Storage contention prevented acquiring the required transactional lock.",
        retryable=True,
    ),
    DomainErrorCode.INTERNAL: DomainErrorSpec(
        DomainErrorCode.INTERNAL,
        "internal",
        "Unexpected internal failure; no unauthorized success effects may commit.",
        retryable=True,
    ),
}


# M0 control-plane exception class names → M1 catalog codes for adapter mapping.
ADAPTER_ERROR_MAP: Final[dict[str, DomainErrorCode]] = {
    "ValidationError": DomainErrorCode.MALFORMED_COMMAND,
    "ConflictError": DomainErrorCode.IDEMPOTENCY_CONFLICT,
    "NotFoundError": DomainErrorCode.NOT_FOUND,
    "ContentionError": DomainErrorCode.CONTENTION,
}
