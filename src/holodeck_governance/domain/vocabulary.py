"""Canonical M1 vocabulary and module ownership contracts.

This module is the machine-readable ownership map for record families.
Downstream packets implement the named modules; they must not invent parallel
names or relocate ownership without updating this contract and DECISIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class RecordOwnership:
    """Ownership for one typed governance record family."""

    record: str
    family: str
    domain_module: str
    persistence_contract: str
    implementing_packet: str
    notes: str = ""


# Layer package roots used by architecture tests.
DOMAIN_ROOT: Final = "holodeck_governance.domain"
APPLICATION_ROOT: Final = "holodeck_governance.application"
STORAGE_ROOT: Final = "holodeck_governance.storage"
ADAPTER_ROOT: Final = "holodeck_control_plane"

FORBIDDEN_DOMAIN_IMPORT_PREFIXES: Final[tuple[str, ...]] = (
    "holodeck_governance.application",
    "holodeck_governance.storage",
    "holodeck_control_plane",
    "sqlite3",
    "http.server",
    "http.client",
    "urllib",
    "mcp",
)

RECORD_OWNERSHIP: Final[tuple[RecordOwnership, ...]] = (
    # Identity and authority
    RecordOwnership(
        "Tenant",
        "identity_authority",
        "holodeck_governance.domain.tenant",
        "TenantRepository",
        "M1-003",
    ),
    RecordOwnership(
        "Actor",
        "identity_authority",
        "holodeck_governance.domain.authority.actors",
        "ActorRepository",
        "M1-010",
    ),
    RecordOwnership(
        "RoleProfile",
        "identity_authority",
        "holodeck_governance.domain.authority.roles",
        "RoleProfileRepository",
        "M1-010",
    ),
    RecordOwnership(
        "RoleAssignment",
        "identity_authority",
        "holodeck_governance.domain.authority.assignments",
        "RoleAssignmentRepository",
        "M1-011",
    ),
    RecordOwnership(
        "DelegatedGrant",
        "identity_authority",
        "holodeck_governance.domain.authority.grants",
        "DelegatedGrantRepository",
        "M1-012",
    ),
    RecordOwnership(
        "RevocationDecision",
        "identity_authority",
        "holodeck_governance.domain.authority.grants",
        "RevocationDecisionRepository",
        "M1-012",
    ),
    # Work vocabulary
    RecordOwnership(
        "Workspace",
        "work_vocabulary",
        "holodeck_governance.domain.records.workspace",
        "WorkspaceRepository",
        "M1-027",
        notes="M1 typed workspace is distinct from M0 coordination workspace rows.",
    ),
    RecordOwnership(
        "Source",
        "work_vocabulary",
        "holodeck_governance.domain.records.source",
        "SourceRepository",
        "M1-027",
    ),
    RecordOwnership(
        "Intent",
        "work_vocabulary",
        "holodeck_governance.domain.records.intent",
        "IntentRepository",
        "M1-027",
    ),
    RecordOwnership(
        "Mission",
        "work_vocabulary",
        "holodeck_governance.domain.records.mission",
        "MissionRepository",
        "M1-027",
        notes="Not the thin-slice missions table; that table is legacy_import only.",
    ),
    RecordOwnership(
        "Task",
        "work_vocabulary",
        "holodeck_governance.domain.records.task",
        "TaskRepository",
        "M1-027",
    ),
    RecordOwnership(
        "Requirement",
        "work_vocabulary",
        "holodeck_governance.domain.records.requirement",
        "RequirementRepository",
        "M1-028",
    ),
    RecordOwnership(
        "TestPlan",
        "work_vocabulary",
        "holodeck_governance.domain.records.test_plan",
        "TestPlanRepository",
        "M1-028",
    ),
    RecordOwnership(
        "Run",
        "work_vocabulary",
        "holodeck_governance.domain.records.run",
        "RunRepository",
        "M1-028",
    ),
    RecordOwnership(
        "Artifact",
        "work_vocabulary",
        "holodeck_governance.domain.records.artifact",
        "ArtifactRepository",
        "M1-028",
    ),
    RecordOwnership(
        "Evidence",
        "work_vocabulary",
        "holodeck_governance.domain.records.evidence",
        "EvidenceRepository",
        "M1-028",
        notes="Metadata and content hash only; not thin-slice mission_evidence rows.",
    ),
    RecordOwnership(
        "Review",
        "work_vocabulary",
        "holodeck_governance.domain.records.review",
        "ReviewRepository",
        "M1-029",
    ),
    RecordOwnership(
        "Approval",
        "work_vocabulary",
        "holodeck_governance.domain.records.approval",
        "ApprovalRepository",
        "M1-029",
    ),
    RecordOwnership(
        "Decision",
        "work_vocabulary",
        "holodeck_governance.domain.records.decision",
        "DecisionRepository",
        "M1-029",
    ),
    RecordOwnership(
        "Escalation",
        "work_vocabulary",
        "holodeck_governance.domain.records.escalation",
        "EscalationRepository",
        "M1-029",
    ),
    # Provenance
    RecordOwnership(
        "ExternalReference",
        "provenance",
        "holodeck_governance.domain.provenance.external_reference",
        "ExternalReferenceRepository",
        "M1-008",
    ),
    RecordOwnership(
        "ProvenanceRecord",
        "provenance",
        "holodeck_governance.domain.provenance.provenance",
        "ProvenanceRepository",
        "M1-007",
    ),
    RecordOwnership(
        "TrustClassification",
        "provenance",
        "holodeck_governance.domain.provenance.trust",
        "TrustClassificationRepository",
        "M1-007",
    ),
    RecordOwnership(
        "ValidationDecision",
        "provenance",
        "holodeck_governance.domain.provenance.validation",
        "ValidationDecisionRepository",
        "M1-007",
    ),
    # Governance control
    RecordOwnership(
        "CommandReceipt",
        "governance_control",
        "holodeck_governance.domain.commands.receipt",
        "CommandReceiptRepository",
        "M1-014",
    ),
    RecordOwnership(
        "EvaluationSnapshot",
        "governance_control",
        "holodeck_governance.domain.evaluation.snapshot",
        "EvaluationSnapshotRepository",
        "M1-017",
    ),
    RecordOwnership(
        "EvaluationResult",
        "governance_control",
        "holodeck_governance.domain.evaluation.result",
        "EvaluationResultRepository",
        "M1-017",
    ),
    RecordOwnership(
        "PolicyBinding",
        "governance_control",
        "holodeck_governance.domain.policy.binding",
        "PolicyBindingRepository",
        "M1-018",
    ),
    RecordOwnership(
        "OverrideDecision",
        "governance_control",
        "holodeck_governance.domain.policy.override",
        "OverrideDecisionRepository",
        "M1-018",
    ),
    RecordOwnership(
        "TransitionRecord",
        "governance_control",
        "holodeck_governance.domain.lifecycle",
        "TransitionRecordRepository",
        "M1-013",
    ),
    # Audit and delivery
    RecordOwnership(
        "DomainEvent",
        "audit_delivery",
        "holodeck_governance.domain.events.ledger",
        "DomainEventRepository",
        "M1-019",
    ),
    RecordOwnership(
        "OutboxItem",
        "audit_delivery",
        "holodeck_governance.domain.events.outbox",
        "OutboxItemRepository",
        "M1-020",
    ),
    RecordOwnership(
        "OutboxAttempt",
        "audit_delivery",
        "holodeck_governance.domain.events.outbox",
        "OutboxAttemptRepository",
        "M1-021",
    ),
    # Cross-cutting primitives owned by dedicated packets
    RecordOwnership(
        "GovernanceObject",
        "cross_cutting",
        "holodeck_governance.domain.registry",
        "GovernanceObjectRepository",
        "M1-005",
        notes="Typed object registry backing revisions and edges.",
    ),
    RecordOwnership(
        "ObjectRevision",
        "cross_cutting",
        "holodeck_governance.domain.revisions",
        "ObjectRevisionRepository",
        "M1-005",
    ),
    RecordOwnership(
        "TraceabilityEdge",
        "cross_cutting",
        "holodeck_governance.domain.edges",
        "TraceabilityEdgeRepository",
        "M1-009",
    ),
)


SHARED_METADATA_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "tenant_id",
    "schema_version",
    "created_at",
    "created_by_actor_id",
    "provenance_ref",
)

REQUIRED_SHARED_METADATA_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "tenant_id",
    "schema_version",
    "created_at",
    "created_by_actor_id",
)

REVISIONED_METADATA_FIELDS: Final[tuple[str, ...]] = (
    "object_id",
    "revision",
    "supersedes_revision",
    "content_hash",
)

OPAQUE_ID_MODULE: Final = "holodeck_governance.domain.ids"
SHARED_METADATA_MODULE: Final = "holodeck_governance.domain.metadata"
OPAQUE_ID_PACKET: Final = "M1-004"

CATALOG_MODULES: Final[dict[str, str]] = {
    "domain_errors": "holodeck_governance.domain.catalogs.errors",
    "reason_codes": "holodeck_governance.domain.catalogs.reasons",
    "event_schemas": "holodeck_governance.domain.catalogs.events",
    "implementing_packet": "M1-031",
}

REPOSITORY_UNIT_OF_WORK: Final[dict[str, str]] = {
    "protocols": "holodeck_governance.storage.protocols",
    "unit_of_work": "holodeck_governance.application.unit_of_work",
    "sqlite_impl": "holodeck_governance.storage.sqlite",
    "implementing_packet": "M1-030",
}

LEGACY_MIGRATION_SEAMS: Final[dict[str, str]] = {
    "legacy_seam_module": "holodeck_governance.storage.legacy_seam",
    "legacy_import_mapping_packet": "M1-006",
    "legacy_migration_proof_packet": "M1-023",
    "m0_store": "holodeck_control_plane.store",
    "m0_migrations": "holodeck_control_plane.migrations",
}


def ownership_by_record() -> dict[str, RecordOwnership]:
    return {item.record: item for item in RECORD_OWNERSHIP}


def records_for_packet(packet_id: str) -> tuple[RecordOwnership, ...]:
    return tuple(item for item in RECORD_OWNERSHIP if item.implementing_packet == packet_id)
