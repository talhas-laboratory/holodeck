"""Domain event type and payload-schema catalog."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


CATALOG_VERSION: Final = "m1.events.v1"


class EventType(StrEnum):
    """Stable event type identifiers emitted by the governance kernel."""

    COMMAND_RECEIVED = "governance.command.received"
    COMMAND_REJECTED = "governance.command.rejected"
    COMMAND_ACCEPTED = "governance.command.accepted"
    EVALUATION_COMPLETED = "governance.evaluation.completed"
    TRANSITION_RECORDED = "governance.transition.recorded"
    REVISION_CREATED = "governance.revision.created"
    GRANT_REVOKED = "governance.grant.revoked"
    POLICY_BINDING_ACTIVATED = "governance.policy_binding.activated"
    OUTBOX_ENQUEUED = "governance.outbox.enqueued"
    OUTBOX_ATTEMPTED = "governance.outbox.attempted"
    OUTBOX_DEAD_LETTERED = "governance.outbox.dead_lettered"
    ESCALATION_CREATED = "governance.escalation.created"
    LEGACY_RECORD_IMPORTED = "governance.legacy.imported"


# Causal metadata required on every domain event payload envelope.
EVENT_ENVELOPE_FIELDS: Final[tuple[str, ...]] = (
    "event_id",
    "tenant_id",
    "ledger_sequence",
    "event_type",
    "occurred_at",
    "actor_id",
    "correlation_id",
    "causation_id",
    "payload_schema_version",
    "subject_refs",
)


@dataclass(frozen=True, slots=True)
class EventSchemaSpec:
    event_type: EventType
    payload_schema_version: str
    required_payload_fields: tuple[str, ...]
    summary: str


EVENT_SCHEMAS: Final[dict[EventType, EventSchemaSpec]] = {
    EventType.COMMAND_RECEIVED: EventSchemaSpec(
        EventType.COMMAND_RECEIVED,
        "m1.event.command_received.v1",
        ("command_id", "command_type", "idempotency_key"),
        "Command envelope accepted for evaluation.",
    ),
    EventType.COMMAND_REJECTED: EventSchemaSpec(
        EventType.COMMAND_REJECTED,
        "m1.event.command_rejected.v1",
        ("command_id", "receipt_id", "error_code", "reason_codes"),
        "Command rejected; no success transition/outbox effects.",
    ),
    EventType.COMMAND_ACCEPTED: EventSchemaSpec(
        EventType.COMMAND_ACCEPTED,
        "m1.event.command_accepted.v1",
        ("command_id", "receipt_id", "evaluation_result_id"),
        "Command permitted after evaluation.",
    ),
    EventType.EVALUATION_COMPLETED: EventSchemaSpec(
        EventType.EVALUATION_COMPLETED,
        "m1.event.evaluation_completed.v1",
        ("evaluation_result_id", "snapshot_id", "outcome", "reason_codes"),
        "Immutable evaluation result recorded.",
    ),
    EventType.TRANSITION_RECORDED: EventSchemaSpec(
        EventType.TRANSITION_RECORDED,
        "m1.event.transition_recorded.v1",
        ("transition_id", "subject_object_id", "from_state", "to_state", "definition_version"),
        "Versioned lifecycle transition appended.",
    ),
    EventType.REVISION_CREATED: EventSchemaSpec(
        EventType.REVISION_CREATED,
        "m1.event.revision_created.v1",
        ("object_id", "revision", "supersedes_revision", "content_hash"),
        "New immutable object revision created.",
    ),
    EventType.GRANT_REVOKED: EventSchemaSpec(
        EventType.GRANT_REVOKED,
        "m1.event.grant_revoked.v1",
        ("grant_id", "revocation_decision_id"),
        "Delegated grant revoked by decision.",
    ),
    EventType.POLICY_BINDING_ACTIVATED: EventSchemaSpec(
        EventType.POLICY_BINDING_ACTIVATED,
        "m1.event.policy_binding_activated.v1",
        ("policy_binding_id", "scope", "effective_from"),
        "Versioned policy binding activated.",
    ),
    EventType.OUTBOX_ENQUEUED: EventSchemaSpec(
        EventType.OUTBOX_ENQUEUED,
        "m1.event.outbox_enqueued.v1",
        ("outbox_item_id", "domain_event_id", "delivery_purpose", "dedup_key"),
        "Outbox delivery obligation created atomically with its event.",
    ),
    EventType.OUTBOX_ATTEMPTED: EventSchemaSpec(
        EventType.OUTBOX_ATTEMPTED,
        "m1.event.outbox_attempted.v1",
        ("outbox_item_id", "attempt_id", "attempt_number", "result"),
        "Outbox delivery attempt appended.",
    ),
    EventType.OUTBOX_DEAD_LETTERED: EventSchemaSpec(
        EventType.OUTBOX_DEAD_LETTERED,
        "m1.event.outbox_dead_lettered.v1",
        ("outbox_item_id", "attempt_count", "escalation_id"),
        "Outbox item entered durable dead-letter state.",
    ),
    EventType.ESCALATION_CREATED: EventSchemaSpec(
        EventType.ESCALATION_CREATED,
        "m1.event.escalation_created.v1",
        ("escalation_id", "subject_refs", "trigger"),
        "Escalation record created without reversing prior decisions.",
    ),
    EventType.LEGACY_RECORD_IMPORTED: EventSchemaSpec(
        EventType.LEGACY_RECORD_IMPORTED,
        "m1.event.legacy_imported.v1",
        ("legacy_table", "legacy_id", "m1_object_id", "provenance_kind"),
        "Legacy row imported with explicit provenance and no invented authority.",
    ),
}
