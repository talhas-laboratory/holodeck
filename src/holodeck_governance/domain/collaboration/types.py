"""Shared collaboration enums and constants."""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Mapping

AdapterMetadata = Mapping[str, str]

INTAKE_ADDRESS_TOKEN: Final = "holodeck"
INTAKE_VERB_WORK: Final = "work"

# Contractual M2 command types submitted through GovernanceApplicationService.
M2_COMMAND_RECEIPT_RECORD: Final = "collaboration.receipt.record"
M2_COMMAND_ORIGIN_RECORD: Final = "collaboration.origin.record"
M2_COMMAND_OUTBOUND_ENQUEUE: Final = "collaboration.outbound.enqueue"

STABLE_INBOUND_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "inbound_event_id",
        "tenant_id",
        "provider",
        "external_event_id",
        "occurred_at",
        "received_at",
        "verified_actor",
        "location",
        "body_text",
        "attachments",
        "source_reference",
    }
)
ADAPTER_METADATA_FIELD: Final = "adapter_metadata"


class VerificationResult(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    UNSIGNED = "unsigned"


class ProcessingOutcome(StrEnum):
    ACCEPTED_ORIGIN = "accepted_origin"
    REJECTED = "rejected"
    IGNORED_NON_INTAKE = "ignored_non_intake"
    DUPLICATE_REPLAY = "duplicate_replay"
    AUTH_FAILED = "auth_failed"


class LocationKind(StrEnum):
    COMMUNITY = "community"
    CHANNEL = "channel"
    THREAD = "thread"
    DM = "dm"
    PROJECT = "project"
