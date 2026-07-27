"""Delegated grants with expiry and revocation (M1-012 / GS-004)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.errors import GovernanceError, MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id


class GrantExpiredError(GovernanceError):
    code = DomainErrorCode.GRANT_EXPIRED


class GrantRevokedError(GovernanceError):
    code = DomainErrorCode.GRANT_REVOKED


class GrantWrongRevisionError(GovernanceError):
    code = DomainErrorCode.GRANT_WRONG_REVISION


@dataclass(frozen=True, slots=True)
class DelegatedGrant:
    grant_id: str
    tenant_id: str
    delegator_actor_id: str
    recipient_actor_id: str
    permission: str
    subject_object_id: str
    subject_revision: int
    effective_from: datetime
    expires_at: datetime
    created_at: datetime
    created_by_actor_id: str
    issuance_basis_kind: str = "role_assignment"
    issuance_basis_id: str | None = None
    redelegatable: bool = False
    schema_version: str = "m1.delegated_grant.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("grant_id", self.grant_id),
            ("tenant_id", self.tenant_id),
            ("delegator_actor_id", self.delegator_actor_id),
            ("recipient_actor_id", self.recipient_actor_id),
            ("subject_object_id", self.subject_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        if self.subject_revision < 1 or not self.permission.strip():
            raise MalformedCommandError("grant permission/revision invalid")
        if self.issuance_basis_id is not None and self.issuance_basis_kind not in {"role_assignment", "parent_grant"}:
            raise MalformedCommandError("grant issuance basis kind invalid")
        if self.issuance_basis_id is not None:
            require_opaque_id(self.issuance_basis_id, "issuance_basis_id")
        for stamp in (self.effective_from, self.expires_at, self.created_at):
            if stamp.tzinfo is None:
                raise MalformedCommandError("grant timestamps must be timezone-aware UTC")
        if self.expires_at <= self.effective_from:
            raise MalformedCommandError("grant expiry must be after effective_from")


@dataclass(frozen=True, slots=True)
class RevocationDecision:
    revocation_id: str
    tenant_id: str
    grant_id: str
    created_at: datetime
    created_by_actor_id: str
    issuance_basis_kind: str = "delegator"
    issuance_basis_id: str | None = None
    rationale: str = ""
    schema_version: str = "m1.revocation_decision.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("revocation_id", self.revocation_id),
            ("tenant_id", self.tenant_id),
            ("grant_id", self.grant_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")
        if self.issuance_basis_id is not None and self.issuance_basis_kind not in {"delegator", "role_assignment"}:
            raise MalformedCommandError("revocation issuance basis kind invalid")
        if self.issuance_basis_id is not None:
            require_opaque_id(self.issuance_basis_id, "issuance_basis_id")


def assert_grant_authorizes(
    grant: DelegatedGrant,
    *,
    at: datetime,
    recipient_actor_id: str,
    subject_object_id: str,
    subject_revision: int,
    permission: str,
    revocation: RevocationDecision | None = None,
) -> None:
    if revocation is not None and revocation.grant_id == grant.grant_id:
        raise GrantRevokedError(f"grant {grant.grant_id} revoked")
    if at < grant.effective_from or at >= grant.expires_at:
        raise GrantExpiredError(f"grant {grant.grant_id} not effective at {at.isoformat()}")
    if grant.recipient_actor_id != recipient_actor_id:
        raise GrantWrongRevisionError("grant recipient mismatch")
    if grant.subject_object_id != subject_object_id:
        raise GrantWrongRevisionError("grant subject mismatch")
    if grant.subject_revision != subject_revision:
        raise GrantWrongRevisionError(
            f"grant targets revision {grant.subject_revision}, not {subject_revision}"
        )
    if grant.permission != permission:
        raise GrantWrongRevisionError("grant permission mismatch")
