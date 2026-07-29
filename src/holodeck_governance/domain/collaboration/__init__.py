"""Provider-neutral collaboration contracts for M2 intake.

Must not import application, storage, sqlite3, HTTP, MCP, or provider SDKs.
"""

from __future__ import annotations

from holodeck_governance.domain.collaboration.adapter import (
    CollaborationAdapter,
    CollaborationAdapterAuthError,
)
from holodeck_governance.domain.collaboration.bindings import (
    BindingStatus,
    CollaborationEndpoint,
    ExternalActorMapping,
    actor_mapping_dedupe_key,
    endpoint_dedupe_key,
)
from holodeck_governance.domain.collaboration.inbound import (
    AttachmentRef,
    ConversationLocation,
    NormalizedInboundEvent,
    VerifiedActorIdentity,
)
from holodeck_governance.domain.collaboration.intake import (
    IntakeCommand,
    IntakePolicyInputs,
    parse_intake_command,
)
from holodeck_governance.domain.collaboration.origins import (
    TaskOrigin,
    task_origin_dedupe_key,
)
from holodeck_governance.domain.collaboration.outbound import (
    OutboundCollaborationMessage,
    outbound_idempotency_key,
)
from holodeck_governance.domain.collaboration.receipts import (
    InboundEventReceipt,
    inbound_receipt_dedupe_key,
)
from holodeck_governance.domain.collaboration.scenario_catalog import (
    CIS_EXPECTATIONS,
    CollaborationScenarioExpectation,
    required_scenario_ids,
)
from holodeck_governance.domain.collaboration.types import (
    ADAPTER_METADATA_FIELD,
    INTAKE_ADDRESS_TOKEN,
    INTAKE_VERB_WORK,
    M2_COMMAND_ORIGIN_RECORD,
    M2_COMMAND_OUTBOUND_ENQUEUE,
    M2_COMMAND_RECEIPT_RECORD,
    STABLE_INBOUND_FIELDS,
    AdapterMetadata,
    LocationKind,
    ProcessingOutcome,
    VerificationResult,
)

__all__ = [
    "ADAPTER_METADATA_FIELD",
    "INTAKE_ADDRESS_TOKEN",
    "INTAKE_VERB_WORK",
    "M2_COMMAND_ORIGIN_RECORD",
    "M2_COMMAND_OUTBOUND_ENQUEUE",
    "M2_COMMAND_RECEIPT_RECORD",
    "STABLE_INBOUND_FIELDS",
    "AdapterMetadata",
    "AttachmentRef",
    "BindingStatus",
    "CIS_EXPECTATIONS",
    "CollaborationAdapter",
    "CollaborationAdapterAuthError",
    "CollaborationEndpoint",
    "CollaborationScenarioExpectation",
    "ConversationLocation",
    "ExternalActorMapping",
    "InboundEventReceipt",
    "IntakeCommand",
    "IntakePolicyInputs",
    "LocationKind",
    "NormalizedInboundEvent",
    "OutboundCollaborationMessage",
    "ProcessingOutcome",
    "TaskOrigin",
    "VerificationResult",
    "VerifiedActorIdentity",
    "actor_mapping_dedupe_key",
    "endpoint_dedupe_key",
    "inbound_receipt_dedupe_key",
    "outbound_idempotency_key",
    "parse_intake_command",
    "required_scenario_ids",
    "task_origin_dedupe_key",
]
