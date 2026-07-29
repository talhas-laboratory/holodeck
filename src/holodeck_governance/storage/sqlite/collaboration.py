"""SQLite persistence for collaboration endpoints, mappings, receipts, and outbound."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from holodeck_governance.domain.catalogs.events import EVENT_SCHEMAS, EventType
from holodeck_governance.domain.collaboration.bindings import (
    BindingStatus,
    CollaborationEndpoint,
    ExternalActorMapping,
)
from holodeck_governance.domain.collaboration.inbound import ConversationLocation
from holodeck_governance.domain.collaboration.origins import TaskOrigin
from holodeck_governance.domain.collaboration.outbound import OutboundCollaborationMessage
from holodeck_governance.domain.collaboration.receipts import InboundEventReceipt
from holodeck_governance.domain.collaboration.types import (
    LocationKind,
    ProcessingOutcome,
    VerificationResult,
)
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    IdempotencyConflictError,
    MalformedCommandError,
    MissingAuthorityError,
    NotFoundGovernanceError,
    RevisionImmutableError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace.bindings import (
    CollaborationLocationBinding,
    RepositoryBinding,
    WorkspaceBindingStatus,
)
from holodeck_governance.domain.workspace.genesis import (
    GenesisDecisionOutcome,
    GenesisProposalStatus,
    WorkspaceGenesisProposal,
)
from holodeck_governance.storage.sqlite.graph_seed import persist_external_reference
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.repos import (
    SqliteDomainEventRepository,
    SqliteOutboxRepository,
)
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository

COLLABORATION_STATUS_DELIVERY_PURPOSE = "collaboration_status"


def _insert_immutable(conn: sqlite3.Connection, sql: str, params: tuple) -> None:
    try:
        conn.execute(sql, params)
    except sqlite3.IntegrityError as exc:
        raise RevisionImmutableError(
            "collaboration record already exists and cannot be overwritten"
        ) from exc


class SqliteCollaborationRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._tx_depth = 0
        migrate_governance(conn)
        self._conn.execute("PRAGMA foreign_keys = ON")

    def _commit_write(self) -> None:
        """Persist writes for file-backed connections unless a caller owns a txn."""

        if self._tx_depth == 0:
            self._conn.commit()

    def _begin_write(self) -> str | None:
        previous = self._conn.isolation_level
        self._conn.isolation_level = None
        self._conn.execute("BEGIN IMMEDIATE")
        self._tx_depth += 1
        return previous

    def _commit_txn(self, previous: str | None) -> None:
        self._conn.execute("COMMIT")
        self._tx_depth = max(0, self._tx_depth - 1)
        self._conn.isolation_level = previous

    def _rollback_txn(self, previous: str | None) -> None:
        self._conn.execute("ROLLBACK")
        self._tx_depth = max(0, self._tx_depth - 1)
        self._conn.isolation_level = previous

    def save_endpoint(self, endpoint: CollaborationEndpoint) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_collaboration_endpoints(
                endpoint_id, tenant_id, provider, external_endpoint_id, locator,
                display_name, status, created_at, created_by_actor_id,
                adapter_metadata_json, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                endpoint.endpoint_id,
                endpoint.tenant_id,
                endpoint.provider,
                endpoint.external_endpoint_id,
                endpoint.locator,
                endpoint.display_name,
                endpoint.status.value,
                endpoint.created_at.isoformat(),
                endpoint.created_by_actor_id,
                json.dumps(dict(endpoint.adapter_metadata), sort_keys=True),
                endpoint.schema_version,
            ),
        )
        self._commit_write()

    def get_endpoint(self, endpoint_id: str) -> CollaborationEndpoint | None:
        row = self._conn.execute(
            "SELECT * FROM gov_collaboration_endpoints WHERE endpoint_id = ?",
            (endpoint_id,),
        ).fetchone()
        return None if row is None else self._endpoint_from_row(row)

    def get_endpoint_by_external(
        self, *, tenant_id: str, provider: str, external_endpoint_id: str
    ) -> CollaborationEndpoint | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_collaboration_endpoints
            WHERE tenant_id = ? AND provider = ? AND external_endpoint_id = ?
            """,
            (tenant_id, provider, external_endpoint_id),
        ).fetchone()
        return None if row is None else self._endpoint_from_row(row)

    def require_endpoint(self, endpoint_id: str, *, tenant_id: str) -> CollaborationEndpoint:
        endpoint = self.get_endpoint(endpoint_id)
        if endpoint is None:
            raise NotFoundGovernanceError(f"unknown collaboration endpoint {endpoint_id}")
        if endpoint.tenant_id != tenant_id:
            raise CrossTenantAccessError("collaboration endpoint tenant mismatch")
        return endpoint

    def require_active_endpoint(
        self, endpoint_id: str, *, tenant_id: str
    ) -> CollaborationEndpoint:
        endpoint = self.require_endpoint(endpoint_id, tenant_id=tenant_id)
        if endpoint.status is not BindingStatus.ACTIVE:
            raise MissingAuthorityError("collaboration endpoint is not active")
        return endpoint

    def save_external_reference(self, ref: ExternalReference) -> None:
        existing = self._conn.execute(
            "SELECT reference_id FROM gov_external_references WHERE reference_id = ?",
            (ref.reference_id,),
        ).fetchone()
        if existing is not None:
            return
        dedupe = self._conn.execute(
            """
            SELECT reference_id FROM gov_external_references
            WHERE tenant_id = ? AND provider = ? AND object_type = ? AND external_object_id = ?
            """,
            (ref.tenant_id, ref.provider, ref.object_type, ref.external_object_id),
        ).fetchone()
        if dedupe is not None:
            if str(dedupe["reference_id"]) != ref.reference_id:
                raise IdempotencyConflictError(
                    "external reference dedupe key reused with different reference_id"
                )
            return
        persist_external_reference(self._conn, ref)
        self._commit_write()

    def save_actor_mapping(self, mapping: ExternalActorMapping) -> None:
        self.require_endpoint(mapping.endpoint_id, tenant_id=mapping.tenant_id)
        actor = self._conn.execute(
            "SELECT tenant_id FROM gov_actors WHERE actor_id = ?",
            (mapping.actor_id,),
        ).fetchone()
        if actor is None:
            raise NotFoundGovernanceError(f"unknown actor {mapping.actor_id}")
        if str(actor["tenant_id"]) != mapping.tenant_id:
            raise CrossTenantAccessError("actor mapping tenant mismatch")
        ref = self._conn.execute(
            "SELECT tenant_id FROM gov_external_references WHERE reference_id = ?",
            (mapping.external_identity_reference_id,),
        ).fetchone()
        if ref is None:
            raise NotFoundGovernanceError(
                f"unknown external reference {mapping.external_identity_reference_id}"
            )
        if str(ref["tenant_id"]) != mapping.tenant_id:
            raise CrossTenantAccessError("external identity reference tenant mismatch")
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_external_actor_mappings(
                mapping_id, tenant_id, endpoint_id, actor_id, provider, external_actor_id,
                external_identity_reference_id, status, created_at, created_by_actor_id,
                adapter_metadata_json, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mapping.mapping_id,
                mapping.tenant_id,
                mapping.endpoint_id,
                mapping.actor_id,
                mapping.provider,
                mapping.external_actor_id,
                mapping.external_identity_reference_id,
                mapping.status.value,
                mapping.created_at.isoformat(),
                mapping.created_by_actor_id,
                json.dumps(dict(mapping.adapter_metadata), sort_keys=True),
                mapping.schema_version,
            ),
        )
        self._commit_write()

    def get_actor_mapping(self, mapping_id: str) -> ExternalActorMapping | None:
        row = self._conn.execute(
            "SELECT * FROM gov_external_actor_mappings WHERE mapping_id = ?",
            (mapping_id,),
        ).fetchone()
        return None if row is None else self._mapping_from_row(row)

    def get_active_actor_mapping(
        self,
        *,
        tenant_id: str,
        provider: str,
        actor_id: str,
        endpoint_id: str,
    ) -> ExternalActorMapping | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_external_actor_mappings
            WHERE tenant_id = ?
              AND provider = ?
              AND actor_id = ?
              AND endpoint_id = ?
              AND status = ?
            """,
            (tenant_id, provider, actor_id, endpoint_id, BindingStatus.ACTIVE.value),
        ).fetchone()
        return None if row is None else self._mapping_from_row(row)

    def require_exact_active_actor_mapping(
        self,
        *,
        mapping_id: str,
        tenant_id: str,
        provider: str,
        actor_id: str,
        endpoint_id: str,
        external_actor_id: str,
    ) -> ExternalActorMapping:
        mapping = self.get_actor_mapping(mapping_id)
        if mapping is None:
            raise MissingAuthorityError(
                "accepted intake requires a known external actor mapping"
            )
        if mapping.tenant_id != tenant_id:
            raise CrossTenantAccessError("actor mapping tenant mismatch")
        if mapping.status is not BindingStatus.ACTIVE:
            raise MissingAuthorityError("external actor mapping is not active")
        if (
            mapping.provider != provider
            or mapping.endpoint_id != endpoint_id
            or mapping.actor_id != actor_id
            or mapping.external_actor_id != external_actor_id
        ):
            raise MissingAuthorityError(
                "accepted intake requires the exact active mapping for "
                "endpoint/provider/actor/external_actor"
            )
        return mapping

    def actor_may_intake(
        self, *, tenant_id: str, actor_id: str, at: datetime
    ) -> bool:
        """Tenant-scoped role permission check for collaboration.intake."""

        from holodeck_governance.domain.authority.assignments import (
            RoleAssignment,
            assignment_is_active,
        )

        rows = self._conn.execute(
            """
            SELECT a.*, p.permissions_json
            FROM gov_role_assignments a
            JOIN gov_role_profiles p
              ON p.role_object_id = a.role_object_id AND p.revision = a.role_revision
            WHERE a.tenant_id = ? AND a.actor_id = ?
            """,
            (tenant_id, actor_id),
        ).fetchall()
        for row in rows:
            assignment = RoleAssignment(
                assignment_id=str(row["assignment_id"]),
                tenant_id=str(row["tenant_id"]),
                actor_id=str(row["actor_id"]),
                role_object_id=str(row["role_object_id"]),
                role_revision=int(row["role_revision"]),
                workspace_object_id=row["workspace_object_id"],
                jurisdiction_key=str(row["jurisdiction_key"]),
                jurisdiction_value=str(row["jurisdiction_value"]),
                effective_from=datetime.fromisoformat(str(row["effective_from"])),
                created_at=datetime.fromisoformat(str(row["created_at"])),
                created_by_actor_id=str(row["created_by_actor_id"]),
                effective_until=(
                    datetime.fromisoformat(str(row["effective_until"]))
                    if row["effective_until"] is not None
                    else None
                ),
                schema_version=str(row["schema_version"]),
            )
            if not assignment_is_active(assignment, at=at):
                continue
            if assignment.jurisdiction_key not in {"tenant", "*"}:
                continue
            permissions = set(json.loads(str(row["permissions_json"])))
            if "collaboration.intake" in permissions or "*" in permissions:
                return True
        return False

    def get_actor_mapping_by_external(
        self, *, tenant_id: str, provider: str, external_actor_id: str
    ) -> ExternalActorMapping | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_external_actor_mappings
            WHERE tenant_id = ? AND provider = ? AND external_actor_id = ?
            """,
            (tenant_id, provider, external_actor_id),
        ).fetchone()
        return None if row is None else self._mapping_from_row(row)

    def get_inbound_receipt(self, receipt_id: str) -> InboundEventReceipt | None:
        row = self._conn.execute(
            "SELECT * FROM gov_inbound_event_receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
        return None if row is None else self._receipt_from_row(row)

    def get_inbound_receipt_by_external(
        self, *, tenant_id: str, provider: str, external_event_id: str
    ) -> InboundEventReceipt | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_inbound_event_receipts
            WHERE tenant_id = ? AND provider = ? AND external_event_id = ?
            """,
            (tenant_id, provider, external_event_id),
        ).fetchone()
        return None if row is None else self._receipt_from_row(row)

    def save_inbound_receipt(
        self,
        receipt: InboundEventReceipt,
        *,
        endpoint_id: str | None = None,
    ) -> InboundEventReceipt:
        if endpoint_id is not None:
            self.require_endpoint(endpoint_id, tenant_id=receipt.tenant_id)
        existing = self.get_inbound_receipt_by_external(
            tenant_id=receipt.tenant_id,
            provider=receipt.provider,
            external_event_id=receipt.external_event_id,
        )
        if existing is not None:
            return existing
        ref = self._conn.execute(
            "SELECT tenant_id FROM gov_external_references WHERE reference_id = ?",
            (receipt.signed_source_reference_id,),
        ).fetchone()
        if ref is None:
            raise NotFoundGovernanceError(
                f"unknown source reference {receipt.signed_source_reference_id}"
            )
        if str(ref["tenant_id"]) != receipt.tenant_id:
            raise CrossTenantAccessError("source reference tenant mismatch")
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_inbound_event_receipts(
                receipt_id, tenant_id, provider, external_event_id, inbound_event_id,
                signed_source_reference_id, verification_result, processing_outcome,
                reason_codes_json, checkpoint_token, created_at, command_id,
                task_origin_object_id, endpoint_id, mapping_id, external_actor_id,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.receipt_id,
                receipt.tenant_id,
                receipt.provider,
                receipt.external_event_id,
                receipt.inbound_event_id,
                receipt.signed_source_reference_id,
                receipt.verification_result.value,
                receipt.processing_outcome.value,
                json.dumps(list(receipt.reason_codes)),
                receipt.checkpoint_token,
                receipt.created_at.isoformat(),
                receipt.command_id,
                receipt.task_origin_object_id,
                endpoint_id,
                receipt.mapping_id,
                receipt.external_actor_id,
                receipt.schema_version,
            ),
        )
        self._commit_write()
        return receipt

    def get_task_origin(self, object_id: str) -> TaskOrigin | None:
        row = self._conn.execute(
            "SELECT * FROM gov_task_origins WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        return None if row is None else self._origin_from_row(row)

    def get_task_origin_by_external(
        self, *, tenant_id: str, provider: str, external_event_id: str
    ) -> TaskOrigin | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_task_origins
            WHERE tenant_id = ? AND provider = ? AND external_event_id = ?
            """,
            (tenant_id, provider, external_event_id),
        ).fetchone()
        return None if row is None else self._origin_from_row(row)

    def record_accepted_origin(
        self,
        *,
        origin: TaskOrigin,
        receipt: InboundEventReceipt,
        source_reference: ExternalReference,
        location_reference: ExternalReference,
        parent_location_reference: ExternalReference | None = None,
        endpoint_id: str | None = None,
    ) -> tuple[TaskOrigin, InboundEventReceipt, bool]:
        """Atomically persist accepted intake origin + linked receipt."""

        self._validate_accepted_origin_inputs(
            origin=origin,
            receipt=receipt,
            source_reference=source_reference,
            location_reference=location_reference,
            parent_location_reference=parent_location_reference,
            endpoint_id=endpoint_id,
        )
        existing = self.get_task_origin_by_external(
            tenant_id=origin.tenant_id,
            provider=origin.provider,
            external_event_id=origin.external_event_id,
        )
        if existing is not None:
            prior_receipt = self.get_inbound_receipt_by_external(
                tenant_id=origin.tenant_id,
                provider=origin.provider,
                external_event_id=origin.external_event_id,
            )
            if prior_receipt is None:
                raise NotFoundGovernanceError(
                    "task origin exists without inbound receipt"
                )
            return existing, prior_receipt, False

        prior_receipt = self.get_inbound_receipt_by_external(
            tenant_id=origin.tenant_id,
            provider=origin.provider,
            external_event_id=origin.external_event_id,
        )
        if prior_receipt is not None:
            if (
                prior_receipt.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
                and prior_receipt.task_origin_object_id == origin.object_id
                and prior_receipt.receipt_id == origin.inbound_receipt_id
            ):
                return self._complete_origin_after_receipt(
                    origin=origin,
                    prior_receipt=prior_receipt,
                    source_reference=source_reference,
                    location_reference=location_reference,
                    parent_location_reference=parent_location_reference,
                )
            raise IdempotencyConflictError(
                "inbound receipt exists without a compatible task origin"
            )

        previous = self._begin_write()
        try:
            existing = self.get_task_origin_by_external(
                tenant_id=origin.tenant_id,
                provider=origin.provider,
                external_event_id=origin.external_event_id,
            )
            if existing is not None:
                found_receipt = self.get_inbound_receipt_by_external(
                    tenant_id=origin.tenant_id,
                    provider=origin.provider,
                    external_event_id=origin.external_event_id,
                )
                assert found_receipt is not None
                self._commit_txn(previous)
                return existing, found_receipt, False

            self.save_external_reference(source_reference)
            self.save_external_reference(location_reference)
            if parent_location_reference is not None:
                self.save_external_reference(parent_location_reference)

            revisions = SqliteRevisionRepository(self._conn)
            if revisions.get_object(origin.object_id) is None:
                revisions.register_object(
                    GovernanceObject(
                        object_id=origin.object_id,
                        tenant_id=origin.tenant_id,
                        object_type="TaskOrigin",
                        created_at=origin.created_at,
                        created_by_actor_id=origin.created_by_actor_id,
                    )
                )

            effective_endpoint = endpoint_id or origin.endpoint_id
            self.save_inbound_receipt(receipt, endpoint_id=effective_endpoint)
            self._insert_task_origin(origin)
            self._commit_txn(previous)
            return origin, receipt, True
        except Exception:
            self._rollback_txn(previous)
            raise

    def _complete_origin_after_receipt(
        self,
        *,
        origin: TaskOrigin,
        prior_receipt: InboundEventReceipt,
        source_reference: ExternalReference,
        location_reference: ExternalReference,
        parent_location_reference: ExternalReference | None,
    ) -> tuple[TaskOrigin, InboundEventReceipt, bool]:
        previous = self._begin_write()
        try:
            again = self.get_task_origin_by_external(
                tenant_id=origin.tenant_id,
                provider=origin.provider,
                external_event_id=origin.external_event_id,
            )
            if again is not None:
                self._commit_txn(previous)
                return again, prior_receipt, False
            self.save_external_reference(source_reference)
            self.save_external_reference(location_reference)
            if parent_location_reference is not None:
                self.save_external_reference(parent_location_reference)
            revisions = SqliteRevisionRepository(self._conn)
            if revisions.get_object(origin.object_id) is None:
                revisions.register_object(
                    GovernanceObject(
                        object_id=origin.object_id,
                        tenant_id=origin.tenant_id,
                        object_type="TaskOrigin",
                        created_at=origin.created_at,
                        created_by_actor_id=origin.created_by_actor_id,
                    )
                )
            self._insert_task_origin(origin)
            self._commit_txn(previous)
            return origin, prior_receipt, True
        except Exception:
            self._rollback_txn(previous)
            raise

    def _validate_accepted_origin_inputs(
        self,
        *,
        origin: TaskOrigin,
        receipt: InboundEventReceipt,
        source_reference: ExternalReference,
        location_reference: ExternalReference,
        parent_location_reference: ExternalReference | None,
        endpoint_id: str | None,
    ) -> None:
        if receipt.processing_outcome is not ProcessingOutcome.ACCEPTED_ORIGIN:
            raise MalformedCommandError(
                "task origins require accepted_origin receipts"
            )
        if receipt.verification_result is not VerificationResult.VERIFIED:
            raise MissingAuthorityError(
                "accepted intake requires verified actor identity"
            )
        if receipt.task_origin_object_id != origin.object_id:
            raise MalformedCommandError(
                "receipt.task_origin_object_id must equal origin.object_id"
            )
        if origin.inbound_receipt_id != receipt.receipt_id:
            raise MalformedCommandError(
                "origin.inbound_receipt_id must equal receipt.receipt_id"
            )
        if origin.tenant_id != receipt.tenant_id:
            raise CrossTenantAccessError("origin/receipt tenant mismatch")
        if (
            origin.provider != receipt.provider
            or origin.external_event_id != receipt.external_event_id
        ):
            raise MalformedCommandError("origin external event must match receipt")
        if origin.source_reference_id != source_reference.reference_id:
            raise MalformedCommandError("source_reference must match origin")
        if receipt.signed_source_reference_id != source_reference.reference_id:
            raise MalformedCommandError("source_reference must match receipt")
        if location_reference.reference_id != origin.location_reference_id:
            raise MalformedCommandError("location_reference must match origin")
        for ref in (source_reference, location_reference, parent_location_reference):
            if ref is None:
                continue
            if ref.tenant_id != origin.tenant_id:
                raise CrossTenantAccessError("origin reference tenant mismatch")
        if parent_location_reference is not None:
            if (
                origin.parent_location_reference_id
                != parent_location_reference.reference_id
            ):
                raise MalformedCommandError(
                    "parent_location_reference must match origin"
                )
        elif origin.parent_location_reference_id is not None:
            raise MalformedCommandError(
                "parent_location_reference required when origin has parent id"
            )
        effective_endpoint = endpoint_id or origin.endpoint_id
        if effective_endpoint is None:
            raise MissingAuthorityError(
                "accepted intake requires an active collaboration endpoint"
            )
        if origin.endpoint_id is not None and origin.endpoint_id != effective_endpoint:
            raise MalformedCommandError("origin.endpoint_id must match endpoint_id")
        self.require_active_endpoint(effective_endpoint, tenant_id=origin.tenant_id)
        if receipt.mapping_id is None or receipt.external_actor_id is None:
            raise MalformedCommandError(
                "accepted intake requires mapping_id and external_actor_id on receipt"
            )
        if origin.mapping_id != receipt.mapping_id:
            raise MalformedCommandError(
                "origin.mapping_id must equal receipt.mapping_id"
            )
        self.require_exact_active_actor_mapping(
            mapping_id=origin.mapping_id,
            tenant_id=origin.tenant_id,
            provider=origin.provider,
            actor_id=origin.actor_id,
            endpoint_id=effective_endpoint,
            external_actor_id=receipt.external_actor_id,
        )
        if not self.actor_may_intake(
            tenant_id=origin.tenant_id,
            actor_id=origin.actor_id,
            at=origin.created_at,
        ):
            raise MissingAuthorityError(
                "actor lacks collaboration.intake authority"
            )
        actor = self._conn.execute(
            "SELECT tenant_id FROM gov_actors WHERE actor_id = ?",
            (origin.actor_id,),
        ).fetchone()
        if actor is None:
            raise NotFoundGovernanceError(f"unknown actor {origin.actor_id}")
        if str(actor["tenant_id"]) != origin.tenant_id:
            raise CrossTenantAccessError("origin actor tenant mismatch")

    def get_external_reference(self, reference_id: str) -> ExternalReference | None:
        row = self._conn.execute(
            "SELECT * FROM gov_external_references WHERE reference_id = ?",
            (reference_id,),
        ).fetchone()
        return None if row is None else self._external_reference_from_row(row)

    def get_outbound_message(self, message_id: str) -> OutboundCollaborationMessage | None:
        row = self._conn.execute(
            "SELECT * FROM gov_outbound_collaboration_messages WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        return None if row is None else self._outbound_from_row(row)

    def get_outbound_message_by_idempotency(
        self, *, tenant_id: str, idempotency_key: str
    ) -> tuple[OutboundCollaborationMessage, str] | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_outbound_collaboration_messages
            WHERE tenant_id = ? AND idempotency_key = ?
            """,
            (tenant_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        return self._outbound_from_row(row), str(row["outbox_item_id"])

    def enqueue_outbound_message(
        self, message: OutboundCollaborationMessage
    ) -> tuple[OutboundCollaborationMessage, str, bool]:
        """Persist a correlated outbound message and durable outbox obligation."""

        self._validate_outbound_message(message)
        existing = self.get_outbound_message_by_idempotency(
            tenant_id=message.tenant_id,
            idempotency_key=message.idempotency_key,
        )
        if existing is not None:
            prior, outbox_item_id = existing
            return prior, outbox_item_id, False

        outbox = SqliteOutboxRepository(self._conn)
        prior_outbox = outbox.get_by_dedup(
            tenant_id=message.tenant_id, dedup_key=message.idempotency_key
        )
        if prior_outbox is not None:
            raise IdempotencyConflictError(
                "outbox dedup key exists without outbound collaboration message"
            )

        previous = self._begin_write()
        try:
            existing = self.get_outbound_message_by_idempotency(
                tenant_id=message.tenant_id,
                idempotency_key=message.idempotency_key,
            )
            if existing is not None:
                prior, outbox_item_id = existing
                self._commit_txn(previous)
                return prior, outbox_item_id, False

            destination = message.destination
            self.save_external_reference(destination.external_location)
            if destination.parent_external_location is not None:
                self.save_external_reference(destination.parent_external_location)
            if destination.endpoint_id is not None:
                self.require_endpoint(
                    destination.endpoint_id, tenant_id=message.tenant_id
                )

            origin = self.get_task_origin(message.task_origin_object_id)
            assert origin is not None
            origin_actor_id = origin.actor_id

            event_id = generate_uuidv7()
            outbox_item_id = generate_uuidv7()
            stamp = message.created_at.isoformat()
            events = SqliteDomainEventRepository(self._conn)
            events.append(
                event_id=event_id,
                tenant_id=message.tenant_id,
                event_type=EventType.OUTBOX_ENQUEUED.value,
                correlation_id=message.task_origin_object_id,
                causation_id=message.command_id,
                actor_id=origin_actor_id,
                payload_schema_version=EVENT_SCHEMAS[
                    EventType.OUTBOX_ENQUEUED
                ].payload_schema_version,
                occurred_at=stamp,
                subject_object_id=message.task_origin_object_id,
                payload={
                    "outbox_item_id": outbox_item_id,
                    "domain_event_id": event_id,
                    "delivery_purpose": COLLABORATION_STATUS_DELIVERY_PURPOSE,
                    "dedup_key": message.idempotency_key,
                    "message_id": message.message_id,
                    "inbound_receipt_id": message.inbound_receipt_id,
                },
                created_at=stamp,
            )
            outbox.enqueue(
                tenant_id=message.tenant_id,
                domain_event_id=event_id,
                delivery_purpose=COLLABORATION_STATUS_DELIVERY_PURPOSE,
                dedup_key=message.idempotency_key,
                created_at=stamp,
                outbox_item_id=outbox_item_id,
            )
            parent_id = (
                None
                if destination.parent_external_location is None
                else destination.parent_external_location.reference_id
            )
            _insert_immutable(
                self._conn,
                """
                INSERT INTO gov_outbound_collaboration_messages(
                    message_id, tenant_id, provider, location_kind, location_reference_id,
                    parent_location_reference_id, endpoint_id, body_text,
                    task_origin_object_id, inbound_receipt_id, command_id, idempotency_key,
                    outbox_item_id, domain_event_id, created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.tenant_id,
                    message.provider,
                    destination.location_kind.value,
                    destination.external_location.reference_id,
                    parent_id,
                    destination.endpoint_id,
                    message.body_text,
                    message.task_origin_object_id,
                    message.inbound_receipt_id,
                    message.command_id,
                    message.idempotency_key,
                    outbox_item_id,
                    event_id,
                    stamp,
                    message.schema_version,
                ),
            )
            self._commit_txn(previous)
            return message, outbox_item_id, True
        except Exception:
            self._rollback_txn(previous)
            raise

    def _validate_outbound_message(self, message: OutboundCollaborationMessage) -> None:
        origin = self.get_task_origin(message.task_origin_object_id)
        if origin is None:
            raise NotFoundGovernanceError(
                f"unknown task origin {message.task_origin_object_id}"
            )
        if origin.tenant_id != message.tenant_id:
            raise CrossTenantAccessError("outbound message origin tenant mismatch")
        if origin.provider != message.provider:
            raise MalformedCommandError("outbound provider must match task origin")
        if origin.inbound_receipt_id != message.inbound_receipt_id:
            raise MalformedCommandError(
                "outbound inbound_receipt_id must match task origin"
            )
        receipt = self.get_inbound_receipt(message.inbound_receipt_id)
        if receipt is None:
            raise NotFoundGovernanceError(
                f"unknown inbound receipt {message.inbound_receipt_id}"
            )
        if receipt.tenant_id != message.tenant_id:
            raise CrossTenantAccessError("outbound message receipt tenant mismatch")
        if receipt.processing_outcome is not ProcessingOutcome.ACCEPTED_ORIGIN:
            raise MalformedCommandError(
                "outbound status requires an accepted_origin receipt"
            )
        if receipt.task_origin_object_id != origin.object_id:
            raise MalformedCommandError(
                "receipt task_origin_object_id must match origin"
            )
        if receipt.receipt_id != origin.inbound_receipt_id:
            raise MalformedCommandError(
                "outbound inbound_receipt_id must match task origin"
            )
        destination = message.destination
        if destination.external_location.tenant_id != message.tenant_id:
            raise CrossTenantAccessError("destination tenant mismatch")
        if destination.endpoint_id is not None:
            self.require_endpoint(destination.endpoint_id, tenant_id=message.tenant_id)

    def require_workspace_object(self, workspace_object_id: str, *, tenant_id: str) -> None:
        row = self._conn.execute(
            """
            SELECT object_id, tenant_id, object_type FROM gov_objects
            WHERE object_id = ?
            """,
            (workspace_object_id,),
        ).fetchone()
        if row is None:
            raise NotFoundGovernanceError(f"unknown workspace {workspace_object_id}")
        if str(row["tenant_id"]) != tenant_id:
            raise CrossTenantAccessError("workspace tenant mismatch")
        if str(row["object_type"]) != "Workspace":
            raise MalformedCommandError(
                f"object {workspace_object_id} is not a Workspace"
            )

    def save_repository_binding(self, binding: RepositoryBinding) -> None:
        self.require_workspace_object(
            binding.workspace_object_id, tenant_id=binding.tenant_id
        )
        ref = self.get_external_reference(binding.external_reference_id)
        if ref is None:
            raise NotFoundGovernanceError(
                f"unknown external reference {binding.external_reference_id}"
            )
        if ref.tenant_id != binding.tenant_id:
            raise CrossTenantAccessError("repository binding reference tenant mismatch")
        actor = self._conn.execute(
            "SELECT tenant_id FROM gov_actors WHERE actor_id = ?",
            (binding.created_by_actor_id,),
        ).fetchone()
        if actor is None:
            raise NotFoundGovernanceError(
                f"unknown actor {binding.created_by_actor_id}"
            )
        if str(actor["tenant_id"]) != binding.tenant_id:
            raise CrossTenantAccessError("repository binding actor tenant mismatch")
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_repository_bindings(
                binding_id, tenant_id, workspace_object_id, provider,
                external_repository_id, canonical_locator, default_branch, status,
                external_reference_id, created_at, created_by_actor_id, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding.binding_id,
                binding.tenant_id,
                binding.workspace_object_id,
                binding.provider,
                binding.external_repository_id,
                binding.canonical_locator,
                binding.default_branch,
                binding.status.value,
                binding.external_reference_id,
                binding.created_at.isoformat(),
                binding.created_by_actor_id,
                binding.schema_version,
            ),
        )
        self._commit_write()

    def get_repository_binding(self, binding_id: str) -> RepositoryBinding | None:
        row = self._conn.execute(
            "SELECT * FROM gov_repository_bindings WHERE binding_id = ?",
            (binding_id,),
        ).fetchone()
        return None if row is None else self._repository_binding_from_row(row)

    def resolve_active_repository_binding(
        self, *, tenant_id: str, provider: str, external_repository_id: str
    ) -> RepositoryBinding | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_repository_bindings
            WHERE tenant_id = ?
              AND provider = ?
              AND external_repository_id = ?
              AND status = ?
            """,
            (
                tenant_id,
                provider,
                external_repository_id,
                WorkspaceBindingStatus.ACTIVE.value,
            ),
        ).fetchone()
        return None if row is None else self._repository_binding_from_row(row)

    def set_repository_binding_status(
        self, binding_id: str, *, tenant_id: str, status: WorkspaceBindingStatus
    ) -> RepositoryBinding:
        binding = self.get_repository_binding(binding_id)
        if binding is None:
            raise NotFoundGovernanceError(f"unknown repository binding {binding_id}")
        if binding.tenant_id != tenant_id:
            raise CrossTenantAccessError("repository binding tenant mismatch")
        self._conn.execute(
            "UPDATE gov_repository_bindings SET status = ? WHERE binding_id = ?",
            (status.value, binding_id),
        )
        self._commit_write()
        updated = self.get_repository_binding(binding_id)
        assert updated is not None
        return updated

    def save_collaboration_location_binding(
        self, binding: CollaborationLocationBinding
    ) -> None:
        self.require_workspace_object(
            binding.workspace_object_id, tenant_id=binding.tenant_id
        )
        self.require_endpoint(binding.endpoint_id, tenant_id=binding.tenant_id)
        ref = self.get_external_reference(binding.location_reference_id)
        if ref is None:
            raise NotFoundGovernanceError(
                f"unknown location reference {binding.location_reference_id}"
            )
        if ref.tenant_id != binding.tenant_id:
            raise CrossTenantAccessError("location binding reference tenant mismatch")
        actor = self._conn.execute(
            "SELECT tenant_id FROM gov_actors WHERE actor_id = ?",
            (binding.created_by_actor_id,),
        ).fetchone()
        if actor is None:
            raise NotFoundGovernanceError(
                f"unknown actor {binding.created_by_actor_id}"
            )
        if str(actor["tenant_id"]) != binding.tenant_id:
            raise CrossTenantAccessError("location binding actor tenant mismatch")
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_collaboration_location_bindings(
                binding_id, tenant_id, workspace_object_id, endpoint_id, location_kind,
                external_location_id, location_reference_id, intake_policy_id, status,
                created_at, created_by_actor_id, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding.binding_id,
                binding.tenant_id,
                binding.workspace_object_id,
                binding.endpoint_id,
                binding.location_kind.value,
                binding.external_location_id,
                binding.location_reference_id,
                binding.intake_policy_id,
                binding.status.value,
                binding.created_at.isoformat(),
                binding.created_by_actor_id,
                binding.schema_version,
            ),
        )
        self._commit_write()

    def get_collaboration_location_binding(
        self, binding_id: str
    ) -> CollaborationLocationBinding | None:
        row = self._conn.execute(
            "SELECT * FROM gov_collaboration_location_bindings WHERE binding_id = ?",
            (binding_id,),
        ).fetchone()
        return None if row is None else self._location_binding_from_row(row)

    def resolve_active_collaboration_location_binding(
        self,
        *,
        tenant_id: str,
        endpoint_id: str,
        location_kind: LocationKind,
        external_location_id: str,
    ) -> CollaborationLocationBinding | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_collaboration_location_bindings
            WHERE tenant_id = ?
              AND endpoint_id = ?
              AND location_kind = ?
              AND external_location_id = ?
              AND status = ?
            """,
            (
                tenant_id,
                endpoint_id,
                location_kind.value,
                external_location_id,
                WorkspaceBindingStatus.ACTIVE.value,
            ),
        ).fetchone()
        return None if row is None else self._location_binding_from_row(row)

    def set_collaboration_location_binding_status(
        self, binding_id: str, *, tenant_id: str, status: WorkspaceBindingStatus
    ) -> CollaborationLocationBinding:
        binding = self.get_collaboration_location_binding(binding_id)
        if binding is None:
            raise NotFoundGovernanceError(
                f"unknown collaboration location binding {binding_id}"
            )
        if binding.tenant_id != tenant_id:
            raise CrossTenantAccessError("location binding tenant mismatch")
        self._conn.execute(
            """
            UPDATE gov_collaboration_location_bindings
            SET status = ? WHERE binding_id = ?
            """,
            (status.value, binding_id),
        )
        self._commit_write()
        updated = self.get_collaboration_location_binding(binding_id)
        assert updated is not None
        return updated

    def get_workspace_status(self, workspace_object_id: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT status FROM gov_workspaces
            WHERE object_id = ?
            ORDER BY revision DESC
            LIMIT 1
            """,
            (workspace_object_id,),
        ).fetchone()
        if row is not None:
            return str(row["status"])
        obj = self._conn.execute(
            "SELECT object_type FROM gov_objects WHERE object_id = ?",
            (workspace_object_id,),
        ).fetchone()
        if obj is None:
            return None
        if str(obj["object_type"]) != "Workspace":
            return None
        return "active"

    def get_workspace_genesis_proposal(
        self, proposal_id: str
    ) -> WorkspaceGenesisProposal | None:
        row = self._conn.execute(
            "SELECT * FROM gov_workspace_genesis_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        return None if row is None else self._genesis_proposal_from_row(row)

    def get_open_workspace_genesis_proposal(
        self,
        *,
        tenant_id: str,
        endpoint_id: str,
        location_kind: LocationKind,
        external_location_id: str,
    ) -> WorkspaceGenesisProposal | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_workspace_genesis_proposals
            WHERE tenant_id = ?
              AND endpoint_id = ?
              AND location_kind = ?
              AND external_location_id = ?
              AND status = ?
            """,
            (
                tenant_id,
                endpoint_id,
                location_kind.value,
                external_location_id,
                GenesisProposalStatus.PROPOSED.value,
            ),
        ).fetchone()
        return None if row is None else self._genesis_proposal_from_row(row)

    def save_workspace_genesis_proposal(
        self, proposal: WorkspaceGenesisProposal
    ) -> None:
        if proposal.status is not GenesisProposalStatus.PROPOSED:
            raise MalformedCommandError(
                "new genesis proposals must start as proposed"
            )
        self.require_endpoint(proposal.endpoint_id, tenant_id=proposal.tenant_id)
        ref = self.get_external_reference(proposal.location_reference_id)
        if ref is None:
            raise NotFoundGovernanceError(
                f"unknown location reference {proposal.location_reference_id}"
            )
        if ref.tenant_id != proposal.tenant_id:
            raise CrossTenantAccessError("genesis location reference tenant mismatch")
        if proposal.repository_reference_id is not None:
            repo_ref = self.get_external_reference(proposal.repository_reference_id)
            if repo_ref is None:
                raise NotFoundGovernanceError(
                    f"unknown repository reference {proposal.repository_reference_id}"
                )
            if repo_ref.tenant_id != proposal.tenant_id:
                raise CrossTenantAccessError(
                    "genesis repository reference tenant mismatch"
                )
        actor = self._conn.execute(
            "SELECT tenant_id FROM gov_actors WHERE actor_id = ?",
            (proposal.created_by_actor_id,),
        ).fetchone()
        if actor is None:
            raise NotFoundGovernanceError(
                f"unknown actor {proposal.created_by_actor_id}"
            )
        if str(actor["tenant_id"]) != proposal.tenant_id:
            raise CrossTenantAccessError("genesis proposal actor tenant mismatch")
        existing_object = self._conn.execute(
            "SELECT object_id FROM gov_objects WHERE object_id = ?",
            (proposal.proposed_workspace_object_id,),
        ).fetchone()
        if existing_object is not None:
            raise MalformedCommandError(
                "proposed_workspace_object_id already exists"
            )
        open_existing = self.get_open_workspace_genesis_proposal(
            tenant_id=proposal.tenant_id,
            endpoint_id=proposal.endpoint_id,
            location_kind=proposal.location_kind,
            external_location_id=proposal.external_location_id,
        )
        if open_existing is not None:
            raise IdempotencyConflictError(
                "an open genesis proposal already exists for this location"
            )
        try:
            self._conn.execute(
                """
                INSERT INTO gov_workspace_genesis_proposals(
                    proposal_id, tenant_id, endpoint_id, location_kind,
                    external_location_id, location_reference_id,
                    proposed_workspace_object_id, display_name, purpose_text, status,
                    discovery_reason_codes_json, repository_provider,
                    external_repository_id, repository_reference_id, created_at,
                    created_by_actor_id, decided_at, decided_by_actor_id,
                    decision_outcome, decision_rationale, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.tenant_id,
                    proposal.endpoint_id,
                    proposal.location_kind.value,
                    proposal.external_location_id,
                    proposal.location_reference_id,
                    proposal.proposed_workspace_object_id,
                    proposal.display_name,
                    proposal.purpose_text,
                    proposal.status.value,
                    json.dumps(list(proposal.discovery_reason_codes)),
                    proposal.repository_provider,
                    proposal.external_repository_id,
                    proposal.repository_reference_id,
                    proposal.created_at.isoformat(),
                    proposal.created_by_actor_id,
                    None,
                    None,
                    None,
                    proposal.decision_rationale,
                    proposal.schema_version,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise IdempotencyConflictError(
                "an open genesis proposal already exists for this location"
            ) from exc
        self._commit_write()

    def decide_workspace_genesis_proposal(
        self,
        *,
        proposal_id: str,
        tenant_id: str,
        outcome: GenesisDecisionOutcome,
        decided_at: datetime,
        decided_by_actor_id: str,
        rationale: str = "",
        repository_canonical_locator: str | None = None,
        repository_default_branch: str | None = None,
    ) -> WorkspaceGenesisProposal:
        proposal = self.get_workspace_genesis_proposal(proposal_id)
        if proposal is None:
            raise NotFoundGovernanceError(f"unknown genesis proposal {proposal_id}")
        if proposal.tenant_id != tenant_id:
            raise CrossTenantAccessError("genesis proposal tenant mismatch")
        if proposal.status is not GenesisProposalStatus.PROPOSED:
            raise MalformedCommandError("genesis proposal is no longer reversible")
        actor = self._conn.execute(
            "SELECT tenant_id FROM gov_actors WHERE actor_id = ?",
            (decided_by_actor_id,),
        ).fetchone()
        if actor is None:
            raise NotFoundGovernanceError(f"unknown actor {decided_by_actor_id}")
        if str(actor["tenant_id"]) != tenant_id:
            raise CrossTenantAccessError("genesis decision actor tenant mismatch")

        if outcome is GenesisDecisionOutcome.WITHDRAW:
            status = GenesisProposalStatus.WITHDRAWN
        elif outcome is GenesisDecisionOutcome.REJECT:
            status = GenesisProposalStatus.REJECTED
        else:
            status = GenesisProposalStatus.APPROVED

        previous = self._begin_write()
        try:
            if outcome is GenesisDecisionOutcome.APPROVE:
                revisions = SqliteRevisionRepository(self._conn)
                revisions.register_object(
                    GovernanceObject(
                        object_id=proposal.proposed_workspace_object_id,
                        tenant_id=proposal.tenant_id,
                        object_type="Workspace",
                        created_at=decided_at,
                        created_by_actor_id=decided_by_actor_id,
                    )
                )
                from holodeck_governance.domain.records.workspace import WorkspaceRecord
                from holodeck_governance.storage.sqlite.records import (
                    SqliteRecordRepository,
                )

                SqliteRecordRepository(self._conn).save_workspace(
                    WorkspaceRecord(
                        record_id=generate_uuidv7(),
                        tenant_id=proposal.tenant_id,
                        object_id=proposal.proposed_workspace_object_id,
                        revision=1,
                        name=proposal.display_name,
                        created_at=decided_at,
                        created_by_actor_id=decided_by_actor_id,
                        status="active",
                    )
                )
                location_binding = CollaborationLocationBinding(
                    binding_id=generate_uuidv7(),
                    tenant_id=proposal.tenant_id,
                    workspace_object_id=proposal.proposed_workspace_object_id,
                    endpoint_id=proposal.endpoint_id,
                    location_kind=proposal.location_kind,
                    external_location_id=proposal.external_location_id,
                    location_reference_id=proposal.location_reference_id,
                    status=WorkspaceBindingStatus.ACTIVE,
                    created_at=decided_at,
                    created_by_actor_id=decided_by_actor_id,
                )
                # Nested write without double-commit: bump tx depth already open.
                self.save_collaboration_location_binding(location_binding)
                if (
                    proposal.repository_provider is not None
                    and proposal.external_repository_id is not None
                    and proposal.repository_reference_id is not None
                ):
                    if (
                        repository_canonical_locator is None
                        or not repository_canonical_locator.strip()
                        or repository_default_branch is None
                        or not repository_default_branch.strip()
                    ):
                        raise MalformedCommandError(
                            "approved genesis with repository requires "
                            "repository_canonical_locator and repository_default_branch"
                        )
                    repo_binding = RepositoryBinding(
                        binding_id=generate_uuidv7(),
                        tenant_id=proposal.tenant_id,
                        workspace_object_id=proposal.proposed_workspace_object_id,
                        provider=proposal.repository_provider,
                        external_repository_id=proposal.external_repository_id,
                        canonical_locator=repository_canonical_locator,
                        default_branch=repository_default_branch,
                        status=WorkspaceBindingStatus.ACTIVE,
                        external_reference_id=proposal.repository_reference_id,
                        created_at=decided_at,
                        created_by_actor_id=decided_by_actor_id,
                    )
                    self.save_repository_binding(repo_binding)

            self._conn.execute(
                """
                UPDATE gov_workspace_genesis_proposals
                SET status = ?, decided_at = ?, decided_by_actor_id = ?,
                    decision_outcome = ?, decision_rationale = ?
                WHERE proposal_id = ? AND status = ?
                """,
                (
                    status.value,
                    decided_at.isoformat(),
                    decided_by_actor_id,
                    outcome.value,
                    rationale,
                    proposal_id,
                    GenesisProposalStatus.PROPOSED.value,
                ),
            )
            if self._conn.total_changes < 1:
                raise MalformedCommandError("genesis proposal is no longer reversible")
            self._commit_txn(previous)
        except Exception:
            self._rollback_txn(previous)
            raise

        updated = self.get_workspace_genesis_proposal(proposal_id)
        assert updated is not None
        return updated

    def _insert_task_origin(self, origin: TaskOrigin) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_task_origins(
                object_id, tenant_id, actor_id, inbound_receipt_id, source_reference_id,
                provider, external_event_id, subject_text, body_text, location_kind,
                location_reference_id, parent_location_reference_id, endpoint_id,
                mapping_id, created_at, created_by_actor_id, adapter_metadata_json,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                origin.object_id,
                origin.tenant_id,
                origin.actor_id,
                origin.inbound_receipt_id,
                origin.source_reference_id,
                origin.provider,
                origin.external_event_id,
                origin.subject_text,
                origin.body_text,
                origin.location_kind.value,
                origin.location_reference_id,
                origin.parent_location_reference_id,
                origin.endpoint_id,
                origin.mapping_id,
                origin.created_at.isoformat(),
                origin.created_by_actor_id,
                json.dumps(dict(origin.adapter_metadata), sort_keys=True),
                origin.schema_version,
            ),
        )

    @staticmethod
    def _origin_from_row(row: sqlite3.Row) -> TaskOrigin:
        parent = row["parent_location_reference_id"]
        endpoint = row["endpoint_id"]
        return TaskOrigin(
            object_id=str(row["object_id"]),
            tenant_id=str(row["tenant_id"]),
            actor_id=str(row["actor_id"]),
            inbound_receipt_id=str(row["inbound_receipt_id"]),
            source_reference_id=str(row["source_reference_id"]),
            provider=str(row["provider"]),
            external_event_id=str(row["external_event_id"]),
            subject_text=str(row["subject_text"]),
            body_text=str(row["body_text"]),
            location_kind=LocationKind(str(row["location_kind"])),
            location_reference_id=str(row["location_reference_id"]),
            mapping_id=str(row["mapping_id"]),
            parent_location_reference_id=None if parent is None else str(parent),
            endpoint_id=None if endpoint is None else str(endpoint),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            adapter_metadata=json.loads(str(row["adapter_metadata_json"])),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _endpoint_from_row(row: sqlite3.Row) -> CollaborationEndpoint:
        return CollaborationEndpoint(
            endpoint_id=str(row["endpoint_id"]),
            tenant_id=str(row["tenant_id"]),
            provider=str(row["provider"]),
            external_endpoint_id=str(row["external_endpoint_id"]),
            locator=str(row["locator"]),
            display_name=str(row["display_name"]),
            status=BindingStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            adapter_metadata=json.loads(str(row["adapter_metadata_json"])),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _mapping_from_row(row: sqlite3.Row) -> ExternalActorMapping:
        return ExternalActorMapping(
            mapping_id=str(row["mapping_id"]),
            tenant_id=str(row["tenant_id"]),
            endpoint_id=str(row["endpoint_id"]),
            actor_id=str(row["actor_id"]),
            provider=str(row["provider"]),
            external_actor_id=str(row["external_actor_id"]),
            external_identity_reference_id=str(row["external_identity_reference_id"]),
            status=BindingStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            adapter_metadata=json.loads(str(row["adapter_metadata_json"])),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _receipt_from_row(row: sqlite3.Row) -> InboundEventReceipt:
        reasons = tuple(json.loads(str(row["reason_codes_json"])))
        origin = row["task_origin_object_id"]
        command = row["command_id"]
        mapping = row["mapping_id"] if "mapping_id" in row.keys() else None
        external_actor = (
            row["external_actor_id"] if "external_actor_id" in row.keys() else None
        )
        return InboundEventReceipt(
            receipt_id=str(row["receipt_id"]),
            tenant_id=str(row["tenant_id"]),
            provider=str(row["provider"]),
            external_event_id=str(row["external_event_id"]),
            inbound_event_id=str(row["inbound_event_id"]),
            signed_source_reference_id=str(row["signed_source_reference_id"]),
            verification_result=VerificationResult(str(row["verification_result"])),
            processing_outcome=ProcessingOutcome(str(row["processing_outcome"])),
            reason_codes=reasons,
            checkpoint_token=str(row["checkpoint_token"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            command_id=None if command is None else str(command),
            task_origin_object_id=None if origin is None else str(origin),
            mapping_id=None if mapping is None else str(mapping),
            external_actor_id=None if external_actor is None else str(external_actor),
            schema_version=str(row["schema_version"]),
        )

    def _outbound_from_row(self, row: sqlite3.Row) -> OutboundCollaborationMessage:
        location = self.get_external_reference(str(row["location_reference_id"]))
        if location is None:
            raise NotFoundGovernanceError(
                f"missing destination reference {row['location_reference_id']}"
            )
        parent_id = row["parent_location_reference_id"]
        parent = None if parent_id is None else self.get_external_reference(str(parent_id))
        endpoint = row["endpoint_id"]
        return OutboundCollaborationMessage(
            message_id=str(row["message_id"]),
            tenant_id=str(row["tenant_id"]),
            provider=str(row["provider"]),
            destination=ConversationLocation(
                location_kind=LocationKind(str(row["location_kind"])),
                external_location=location,
                parent_external_location=parent,
                endpoint_id=None if endpoint is None else str(endpoint),
            ),
            body_text=str(row["body_text"]),
            task_origin_object_id=str(row["task_origin_object_id"]),
            inbound_receipt_id=str(row["inbound_receipt_id"]),
            command_id=str(row["command_id"]),
            idempotency_key=str(row["idempotency_key"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _external_reference_from_row(row: sqlite3.Row) -> ExternalReference:
        subject = row["subject_object_id"]
        content_hash = row["content_hash"]
        return ExternalReference(
            reference_id=str(row["reference_id"]),
            tenant_id=str(row["tenant_id"]),
            provider=str(row["provider"]),
            object_type=str(row["object_type"]),
            external_object_id=str(row["external_object_id"]),
            locator=str(row["locator"]),
            observed_at=datetime.fromisoformat(str(row["observed_at"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            subject_object_id=None if subject is None else str(subject),
            content_hash=None if content_hash is None else str(content_hash),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _repository_binding_from_row(row: sqlite3.Row) -> RepositoryBinding:
        return RepositoryBinding(
            binding_id=str(row["binding_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            provider=str(row["provider"]),
            external_repository_id=str(row["external_repository_id"]),
            canonical_locator=str(row["canonical_locator"]),
            default_branch=str(row["default_branch"]),
            status=WorkspaceBindingStatus(str(row["status"])),
            external_reference_id=str(row["external_reference_id"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _location_binding_from_row(row: sqlite3.Row) -> CollaborationLocationBinding:
        policy = row["intake_policy_id"]
        return CollaborationLocationBinding(
            binding_id=str(row["binding_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            endpoint_id=str(row["endpoint_id"]),
            location_kind=LocationKind(str(row["location_kind"])),
            external_location_id=str(row["external_location_id"]),
            location_reference_id=str(row["location_reference_id"]),
            status=WorkspaceBindingStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            intake_policy_id=None if policy is None else str(policy),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _genesis_proposal_from_row(row: sqlite3.Row) -> WorkspaceGenesisProposal:
        decided_at = row["decided_at"]
        decided_by = row["decided_by_actor_id"]
        decision_outcome = row["decision_outcome"]
        repo_provider = row["repository_provider"]
        repo_id = row["external_repository_id"]
        repo_ref = row["repository_reference_id"]
        return WorkspaceGenesisProposal(
            proposal_id=str(row["proposal_id"]),
            tenant_id=str(row["tenant_id"]),
            endpoint_id=str(row["endpoint_id"]),
            location_kind=LocationKind(str(row["location_kind"])),
            external_location_id=str(row["external_location_id"]),
            location_reference_id=str(row["location_reference_id"]),
            proposed_workspace_object_id=str(row["proposed_workspace_object_id"]),
            display_name=str(row["display_name"]),
            purpose_text=str(row["purpose_text"]),
            status=GenesisProposalStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            discovery_reason_codes=tuple(
                json.loads(str(row["discovery_reason_codes_json"]))
            ),
            repository_provider=None if repo_provider is None else str(repo_provider),
            external_repository_id=None if repo_id is None else str(repo_id),
            repository_reference_id=None if repo_ref is None else str(repo_ref),
            decided_at=(
                None if decided_at is None else datetime.fromisoformat(str(decided_at))
            ),
            decided_by_actor_id=None if decided_by is None else str(decided_by),
            decision_outcome=(
                None
                if decision_outcome is None
                else GenesisDecisionOutcome(str(decision_outcome))
            ),
            decision_rationale=str(row["decision_rationale"]),
            schema_version=str(row["schema_version"]),
        )
