"""Provenance, trust, and validation record types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from holodeck_governance.domain.errors import MalformedCommandError, RevisionImmutableError
from holodeck_governance.domain.ids import require_opaque_id


class TrustClass(StrEnum):
    OBSERVED = "observed"
    CLAIMED = "claimed"
    VALIDATED = "validated"
    LEGACY_IMPORT = "legacy_import"


class EpistemicStatus(StrEnum):
    UNVERIFIED = "unverified"
    CORROBORATED = "corroborated"
    VALIDATED = "validated"
    RETRACTED = "retracted"


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    provenance_id: str
    tenant_id: str
    subject_object_id: str
    origin_kind: str
    created_at: datetime
    created_by_actor_id: str
    derivation_of: str | None = None
    schema_version: str = "m1.provenance.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.provenance_id, "provenance_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.subject_object_id, "subject_object_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if not self.origin_kind.strip():
            raise MalformedCommandError("origin_kind is required")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class TrustClassification:
    trust_id: str
    tenant_id: str
    subject_object_id: str
    trust_class: TrustClass
    epistemic_status: EpistemicStatus
    created_at: datetime
    created_by_actor_id: str
    revision: int = 1
    supersedes_trust_id: str | None = None
    schema_version: str = "m1.trust.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.trust_id, "trust_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.subject_object_id, "subject_object_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if self.revision < 1:
            raise MalformedCommandError("revision must be >= 1")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class ValidationDecision:
    validation_id: str
    tenant_id: str
    subject_object_id: str
    from_trust_id: str
    to_trust_id: str
    decision: str
    created_at: datetime
    created_by_actor_id: str
    rationale: str = ""
    schema_version: str = "m1.validation_decision.v1"

    def __post_init__(self) -> None:
        require_opaque_id(self.validation_id, "validation_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.subject_object_id, "subject_object_id")
        require_opaque_id(self.from_trust_id, "from_trust_id")
        require_opaque_id(self.to_trust_id, "to_trust_id")
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")
        if not self.decision.strip():
            raise MalformedCommandError("decision is required")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")


def reject_trust_in_place_edit(existing: TrustClassification) -> None:
    raise RevisionImmutableError(
        f"trust classification {existing.trust_id} is immutable; promote via validation decision"
    )


def promote_trust(
    *,
    existing: TrustClassification,
    new_trust_id: str,
    validation_id: str,
    actor_id: str,
    created_at: datetime,
    to_trust_class: TrustClass,
    to_epistemic: EpistemicStatus,
    decision: str = "promote",
    rationale: str = "",
) -> tuple[TrustClassification, ValidationDecision]:
    """Create a new trust revision and attributable validation decision."""

    promoted = TrustClassification(
        trust_id=new_trust_id,
        tenant_id=existing.tenant_id,
        subject_object_id=existing.subject_object_id,
        trust_class=to_trust_class,
        epistemic_status=to_epistemic,
        created_at=created_at,
        created_by_actor_id=actor_id,
        revision=existing.revision + 1,
        supersedes_trust_id=existing.trust_id,
    )
    validation = ValidationDecision(
        validation_id=validation_id,
        tenant_id=existing.tenant_id,
        subject_object_id=existing.subject_object_id,
        from_trust_id=existing.trust_id,
        to_trust_id=promoted.trust_id,
        decision=decision,
        created_at=created_at,
        created_by_actor_id=actor_id,
        rationale=rationale,
    )
    return promoted, validation
