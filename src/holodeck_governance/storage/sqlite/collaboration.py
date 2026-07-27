"""SQLite persistence for collaboration endpoints, mappings, and receipts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from holodeck_governance.domain.collaboration.bindings import (
    BindingStatus,
    CollaborationEndpoint,
    ExternalActorMapping,
)
from holodeck_governance.domain.collaboration.origins import TaskOrigin
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
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.graph_seed import persist_external_reference
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository


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
                task_origin_object_id, endpoint_id, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        mapping = self.get_active_actor_mapping(
            tenant_id=origin.tenant_id,
            provider=origin.provider,
            actor_id=origin.actor_id,
            endpoint_id=effective_endpoint,
        )
        if mapping is None:
            raise MissingAuthorityError(
                "accepted intake requires an active external actor mapping"
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

    def _insert_task_origin(self, origin: TaskOrigin) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_task_origins(
                object_id, tenant_id, actor_id, inbound_receipt_id, source_reference_id,
                provider, external_event_id, subject_text, body_text, location_kind,
                location_reference_id, parent_location_reference_id, endpoint_id,
                created_at, created_by_actor_id, adapter_metadata_json, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            schema_version=str(row["schema_version"]),
        )
