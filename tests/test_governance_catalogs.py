"""Catalog validation and scenario coverage tests for M1-031."""

from __future__ import annotations

from holodeck_governance.domain.catalogs import (
    DOMAIN_ERRORS,
    EVENT_SCHEMAS,
    REASON_CODES,
    SCENARIO_CATALOG_EXPECTATIONS,
    DomainErrorCode,
    EventType,
    ReasonCode,
)
from holodeck_governance.domain.catalogs.errors import ADAPTER_ERROR_MAP, CATALOG_VERSION as ERROR_VERSION
from holodeck_governance.domain.catalogs.events import (
    CATALOG_VERSION as EVENT_VERSION,
)
from holodeck_governance.domain.catalogs.events import EVENT_ENVELOPE_FIELDS
from holodeck_governance.domain.catalogs.reasons import CATALOG_VERSION as REASON_VERSION
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    GovernanceError,
    IdempotencyConflictError,
    InvalidTransitionError,
    MalformedCommandError,
    MissingAuthorityError,
    StaleRevisionError,
)


REQUIRED_SCENARIOS = {f"GS-{index:03d}" for index in range(1, 15)}

REQUIRED_ERROR_DISTINCTIONS = {
    DomainErrorCode.INVALID_TRANSITION,
    DomainErrorCode.STALE_REVISION,
    DomainErrorCode.MISSING_AUTHORITY,
    DomainErrorCode.CROSS_TENANT_ACCESS,
    DomainErrorCode.MALFORMED_COMMAND,
    DomainErrorCode.IDEMPOTENCY_CONFLICT,
    DomainErrorCode.INCOMPLETE_EVALUATION,
}


def test_catalog_versions_are_stable() -> None:
    assert ERROR_VERSION == "m1.errors.v1"
    assert REASON_VERSION == "m1.reasons.v1"
    assert EVENT_VERSION == "m1.events.v1"


def test_domain_error_catalog_is_complete_and_unique() -> None:
    assert set(DOMAIN_ERRORS) == set(DomainErrorCode)
    assert len({spec.code for spec in DOMAIN_ERRORS.values()}) == len(DomainErrorCode)


def test_reason_catalog_is_complete_and_unique() -> None:
    assert set(REASON_CODES) == set(ReasonCode)
    assert len({spec.code for spec in REASON_CODES.values()}) == len(ReasonCode)


def test_event_schemas_cover_all_event_types_and_envelope() -> None:
    assert set(EVENT_SCHEMAS) == set(EventType)
    for field in (
        "event_id",
        "tenant_id",
        "ledger_sequence",
        "correlation_id",
        "causation_id",
        "payload_schema_version",
    ):
        assert field in EVENT_ENVELOPE_FIELDS
    for spec in EVENT_SCHEMAS.values():
        assert spec.payload_schema_version.startswith("m1.event.")
        assert spec.required_payload_fields


def test_required_error_distinctions_exist_without_message_parsing() -> None:
    for code in REQUIRED_ERROR_DISTINCTIONS:
        assert code in DOMAIN_ERRORS
        assert DOMAIN_ERRORS[code].code == code


def test_scenario_map_covers_gs_001_through_gs_014() -> None:
    assert set(SCENARIO_CATALOG_EXPECTATIONS) == REQUIRED_SCENARIOS
    for expectation in SCENARIO_CATALOG_EXPECTATIONS.values():
        for code in expectation.primary_error_codes:
            assert code in DOMAIN_ERRORS
        for reason in expectation.primary_reason_codes:
            assert reason in REASON_CODES
        for event_type in expectation.success_event_types:
            assert event_type in EVENT_SCHEMAS
        for event_type in expectation.rejection_must_omit_event_types:
            assert event_type in EVENT_SCHEMAS


def test_rejection_scenarios_declare_absence_of_success_effects() -> None:
    for scenario_id in ("GS-001", "GS-003", "GS-011"):
        expectation = SCENARIO_CATALOG_EXPECTATIONS[scenario_id]
        assert EventType.COMMAND_ACCEPTED in expectation.rejection_must_omit_event_types
        assert EventType.OUTBOX_ENQUEUED in expectation.rejection_must_omit_event_types


def test_adapter_error_map_covers_m0_exception_names() -> None:
    assert ADAPTER_ERROR_MAP["ValidationError"] == DomainErrorCode.MALFORMED_COMMAND
    assert ADAPTER_ERROR_MAP["ConflictError"] == DomainErrorCode.IDEMPOTENCY_CONFLICT
    assert ADAPTER_ERROR_MAP["NotFoundError"] == DomainErrorCode.NOT_FOUND
    assert ADAPTER_ERROR_MAP["ContentionError"] == DomainErrorCode.CONTENTION


def test_typed_exceptions_expose_catalog_codes() -> None:
    cases: list[tuple[GovernanceError, DomainErrorCode]] = [
        (CrossTenantAccessError("denied"), DomainErrorCode.CROSS_TENANT_ACCESS),
        (InvalidTransitionError("bad"), DomainErrorCode.INVALID_TRANSITION),
        (StaleRevisionError("stale"), DomainErrorCode.STALE_REVISION),
        (MissingAuthorityError("no"), DomainErrorCode.MISSING_AUTHORITY),
        (MalformedCommandError("bad"), DomainErrorCode.MALFORMED_COMMAND),
        (IdempotencyConflictError("conflict"), DomainErrorCode.IDEMPOTENCY_CONFLICT),
    ]
    for exc, code in cases:
        assert exc.code == code
        assert str(exc)
