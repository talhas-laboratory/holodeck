"""Domain exception types carrying catalog error codes."""

from __future__ import annotations

from holodeck_governance.domain.catalogs.errors import DomainErrorCode


class GovernanceError(Exception):
    """Base governance-domain error with a stable catalog code."""

    code: DomainErrorCode = DomainErrorCode.INTERNAL

    def __init__(self, message: str, *, code: DomainErrorCode | None = None) -> None:
        self.code = code or type(self).code
        super().__init__(message)


class InvalidTransitionError(GovernanceError):
    code = DomainErrorCode.INVALID_TRANSITION


class StaleRevisionError(GovernanceError):
    code = DomainErrorCode.STALE_REVISION


class MissingAuthorityError(GovernanceError):
    code = DomainErrorCode.MISSING_AUTHORITY


class CrossTenantAccessError(GovernanceError):
    code = DomainErrorCode.CROSS_TENANT_ACCESS


class MalformedCommandError(GovernanceError):
    code = DomainErrorCode.MALFORMED_COMMAND


class IdempotencyConflictError(GovernanceError):
    code = DomainErrorCode.IDEMPOTENCY_CONFLICT


class IncompleteEvaluationError(GovernanceError):
    code = DomainErrorCode.INCOMPLETE_EVALUATION


class RevisionImmutableError(GovernanceError):
    code = DomainErrorCode.REVISION_IMMUTABLE


class ContentionError(GovernanceError):
    code = DomainErrorCode.CONTENTION


class EdgeValidationError(GovernanceError):
    code = DomainErrorCode.EDGE_TYPE_INCOMPATIBLE


class NotFoundGovernanceError(GovernanceError):
    code = DomainErrorCode.NOT_FOUND
