"""Scenario → catalog identifier expectations for GS-001..GS-014."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.catalogs.events import EventType
from holodeck_governance.domain.catalogs.reasons import ReasonCode


@dataclass(frozen=True, slots=True)
class ScenarioCatalogExpectation:
    scenario_id: str
    primary_error_codes: tuple[DomainErrorCode, ...]
    primary_reason_codes: tuple[ReasonCode, ...]
    success_event_types: tuple[EventType, ...]
    rejection_must_omit_event_types: tuple[EventType, ...]
    notes: str = ""


_NO_SUCCESS: Final[tuple[EventType, ...]] = (
    EventType.COMMAND_ACCEPTED,
    EventType.TRANSITION_RECORDED,
    EventType.OUTBOX_ENQUEUED,
)

SCENARIO_CATALOG_EXPECTATIONS: Final[dict[str, ScenarioCatalogExpectation]] = {
    "GS-001": ScenarioCatalogExpectation(
        "GS-001",
        (DomainErrorCode.CROSS_TENANT_ACCESS,),
        (ReasonCode.DENY_TENANT_ISOLATION,),
        (),
        _NO_SUCCESS,
    ),
    "GS-002": ScenarioCatalogExpectation(
        "GS-002",
        (DomainErrorCode.REVISION_IMMUTABLE,),
        (ReasonCode.DENY_REVISION_IMMUTABLE,),
        (EventType.REVISION_CREATED,),
        (),
        notes="Correction path emits revision.created; in-place edit uses error code.",
    ),
    "GS-003": ScenarioCatalogExpectation(
        "GS-003",
        (DomainErrorCode.STALE_REVISION,),
        (ReasonCode.DENY_STALE_APPROVAL,),
        (),
        _NO_SUCCESS,
    ),
    "GS-004": ScenarioCatalogExpectation(
        "GS-004",
        (
            DomainErrorCode.GRANT_EXPIRED,
            DomainErrorCode.GRANT_REVOKED,
            DomainErrorCode.GRANT_WRONG_REVISION,
            DomainErrorCode.MISSING_AUTHORITY,
        ),
        (
            ReasonCode.DENY_GRANT_EXPIRED,
            ReasonCode.DENY_GRANT_REVOKED,
            ReasonCode.DENY_GRANT_WRONG_REVISION,
            ReasonCode.DENY_MISSING_AUTHORITY,
            ReasonCode.ALLOWED,
        ),
        (EventType.COMMAND_ACCEPTED, EventType.TRANSITION_RECORDED),
        _NO_SUCCESS,
    ),
    "GS-005": ScenarioCatalogExpectation(
        "GS-005",
        (
            DomainErrorCode.EDGE_ENDPOINT_MISSING,
            DomainErrorCode.EDGE_TYPE_INCOMPATIBLE,
            DomainErrorCode.CROSS_TENANT_ACCESS,
        ),
        (ReasonCode.DENY_EDGE_INVALID,),
        (),
        (),
    ),
    "GS-006": ScenarioCatalogExpectation(
        "GS-006",
        (DomainErrorCode.INVALID_TRANSITION,),
        (ReasonCode.DENY_INVALID_TRANSITION, ReasonCode.ALLOWED),
        (EventType.TRANSITION_RECORDED,),
        _NO_SUCCESS,
    ),
    "GS-007": ScenarioCatalogExpectation(
        "GS-007",
        (DomainErrorCode.IDEMPOTENCY_CONFLICT,),
        (ReasonCode.DENY_IDEMPOTENCY_CONFLICT, ReasonCode.ALLOWED),
        (EventType.COMMAND_ACCEPTED,),
        _NO_SUCCESS,
    ),
    "GS-008": ScenarioCatalogExpectation(
        "GS-008",
        (),
        (ReasonCode.ALLOWED,),
        (EventType.EVALUATION_COMPLETED,),
        (),
        notes="Reproducibility asserts snapshot/result identity, not a deny code.",
    ),
    "GS-009": ScenarioCatalogExpectation(
        "GS-009",
        (DomainErrorCode.POLICY_UNAUTHORIZED_RELAXATION,),
        (ReasonCode.DENY_POLICY_PRECEDENCE, ReasonCode.ALLOWED),
        (EventType.POLICY_BINDING_ACTIVATED,),
        _NO_SUCCESS,
    ),
    "GS-010": ScenarioCatalogExpectation(
        "GS-010",
        (DomainErrorCode.INTERNAL, DomainErrorCode.CONTENTION),
        (ReasonCode.ALLOWED,),
        (
            EventType.COMMAND_ACCEPTED,
            EventType.EVALUATION_COMPLETED,
            EventType.TRANSITION_RECORDED,
            EventType.OUTBOX_ENQUEUED,
        ),
        _NO_SUCCESS,
        notes="Fault injection must leave either full success set or none.",
    ),
    "GS-011": ScenarioCatalogExpectation(
        "GS-011",
        (
            DomainErrorCode.MISSING_AUTHORITY,
            DomainErrorCode.STALE_REVISION,
            DomainErrorCode.MALFORMED_COMMAND,
            DomainErrorCode.IDEMPOTENCY_CONFLICT,
        ),
        (
            ReasonCode.DENY_MISSING_AUTHORITY,
            ReasonCode.DENY_STALE_REVISION,
            ReasonCode.DENY_MALFORMED_COMMAND,
            ReasonCode.DENY_IDEMPOTENCY_CONFLICT,
        ),
        (EventType.COMMAND_REJECTED, EventType.EVALUATION_COMPLETED),
        _NO_SUCCESS,
    ),
    "GS-012": ScenarioCatalogExpectation(
        "GS-012",
        (),
        (ReasonCode.ESCALATE,),
        (
            EventType.OUTBOX_ATTEMPTED,
            EventType.OUTBOX_DEAD_LETTERED,
            EventType.ESCALATION_CREATED,
        ),
        (),
    ),
    "GS-013": ScenarioCatalogExpectation(
        "GS-013",
        (),
        (ReasonCode.ALLOWED,),
        (
            EventType.COMMAND_ACCEPTED,
            EventType.EVALUATION_COMPLETED,
            EventType.TRANSITION_RECORDED,
        ),
        (),
    ),
    "GS-014": ScenarioCatalogExpectation(
        "GS-014",
        (DomainErrorCode.UNSUPPORTED_LEGACY_MAPPING,),
        (ReasonCode.LEGACY_IMPORT_ONLY,),
        (EventType.LEGACY_RECORD_IMPORTED,),
        (
            EventType.COMMAND_ACCEPTED,
            # Import must not fabricate authority/evidence decision events.
            EventType.GRANT_REVOKED,
            EventType.EVALUATION_COMPLETED,
        ),
    ),
}
