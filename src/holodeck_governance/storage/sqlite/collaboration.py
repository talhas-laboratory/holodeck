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
from holodeck_governance.domain.collaboration.receipts import InboundEventReceipt
from holodeck_governance.domain.collaboration.types import ProcessingOutcome, VerificationResult
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    IdempotencyConflictError,
    NotFoundGovernanceError,
    RevisionImmutableError,
)
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.storage.sqlite.graph_seed import persist_external_reference
from holodeck_governance.storage.sqlite.migrations import migrate_governance


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
        migrate_governance(conn)

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
        return receipt

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
