"""Typed SQLite repository implementations (M1-030)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from holodeck_governance.domain.commands.receipt import CommandReceipt
from holodeck_governance.domain.evaluation.snapshot import EvaluationResult, EvaluationSnapshot
from holodeck_governance.domain.evaluators.primitives import PrimitiveOutcome, PrimitiveResult
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.storage.sqlite.tenants import SqliteTenantRepository

__all__ = [
    "SqliteTenantRepository",
    "SqliteCommandReceiptRepository",
    "SqliteDomainEventRepository",
    "SqliteOutboxRepository",
    "SqliteTransitionRecordRepository",
    "SqliteEvaluationRepository",
]


class SqliteCommandReceiptRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_by_idempotency(
        self, tenant_id: str, idempotency_key: str
    ) -> tuple[str, CommandReceipt] | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_command_receipts
            WHERE tenant_id = ? AND idempotency_key = ?
            """,
            (tenant_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        keys = set(row.keys())
        receipt = CommandReceipt(
            receipt_id=str(row["receipt_id"]),
            command_id=str(row["command_id"]),
            tenant_id=str(row["tenant_id"]),
            outcome=str(row["outcome"]),
            reason_codes=tuple(json.loads(str(row["reason_codes_json"]))),
            error_code=row["error_code"],
            created_at=datetime.fromisoformat(str(row["created_at"])),
            evaluation_result_id=(
                row["evaluation_result_id"] if "evaluation_result_id" in keys else None
            ),
        )
        return str(row["semantic_hash"]), receipt

    def save(
        self,
        receipt: CommandReceipt,
        *,
        idempotency_key: str,
        semantic_hash: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_command_receipts(
                receipt_id, command_id, tenant_id, idempotency_key, semantic_hash,
                outcome, reason_codes_json, error_code, created_at, evaluation_result_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.receipt_id,
                receipt.command_id,
                receipt.tenant_id,
                idempotency_key,
                semantic_hash,
                receipt.outcome,
                json.dumps(list(receipt.reason_codes)),
                receipt.error_code,
                receipt.created_at.isoformat(),
                receipt.evaluation_result_id,
            ),
        )


class SqliteDomainEventRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append(
        self,
        *,
        tenant_id: str,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str,
        causation_id: str,
        created_at: str,
        actor_id: str,
        payload_schema_version: str,
        occurred_at: str | None = None,
        subject_object_id: str | None = None,
        subject_revision: int | None = None,
        subject_refs: dict[str, str] | None = None,
        event_id: str | None = None,
    ) -> str:
        eid = event_id or generate_uuidv7()
        row = self._conn.execute(
            "SELECT COALESCE(MAX(ledger_sequence), 0) + 1 AS seq FROM gov_domain_events WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        seq = int(row[0])
        refs = subject_refs or {}
        if subject_object_id is not None:
            refs = {**refs, "subject_object_id": subject_object_id}
        if subject_revision is not None:
            refs = {**refs, "subject_revision": str(subject_revision)}
        self._conn.execute(
            """
            INSERT INTO gov_domain_events(
                event_id, tenant_id, ledger_sequence, event_type, payload_json,
                correlation_id, causation_id, created_at, actor_id,
                payload_schema_version, occurred_at, subject_object_id,
                subject_revision, subject_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eid,
                tenant_id,
                seq,
                event_type,
                json.dumps(payload, sort_keys=True),
                correlation_id,
                causation_id,
                created_at,
                actor_id,
                payload_schema_version,
                occurred_at or created_at,
                subject_object_id,
                subject_revision,
                json.dumps(refs, sort_keys=True),
            ),
        )
        return eid


class SqliteOutboxRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def enqueue(
        self,
        *,
        tenant_id: str,
        domain_event_id: str,
        delivery_purpose: str,
        dedup_key: str,
        created_at: str,
        outbox_item_id: str | None = None,
    ) -> str:
        item_id = outbox_item_id or generate_uuidv7()
        self._conn.execute(
            """
            INSERT INTO gov_outbox_items(
                outbox_item_id, tenant_id, domain_event_id, delivery_purpose,
                dedup_key, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (item_id, tenant_id, domain_event_id, delivery_purpose, dedup_key, created_at),
        )
        return item_id

    def get_by_dedup(self, *, tenant_id: str, dedup_key: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT outbox_item_id FROM gov_outbox_items
            WHERE tenant_id = ? AND dedup_key = ?
            """,
            (tenant_id, dedup_key),
        ).fetchone()
        return None if row is None else str(row["outbox_item_id"])


class SqliteTransitionRecordRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append(
        self,
        *,
        tenant_id: str,
        subject_object_id: str,
        from_state: str,
        to_state: str,
        definition_version: str,
        created_at: str,
        command_id: str | None = None,
    ) -> str:
        transition_id = generate_uuidv7()
        self._conn.execute(
            """
            INSERT INTO gov_transition_records(
                transition_id, tenant_id, subject_object_id, from_state, to_state,
                definition_version, command_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transition_id,
                tenant_id,
                subject_object_id,
                from_state,
                to_state,
                definition_version,
                command_id or "",
                created_at,
            ),
        )
        return transition_id


def _primitive_to_dict(item: PrimitiveResult) -> dict[str, Any]:
    return {
        "primitive_id": item.primitive_id,
        "outcome": item.outcome.value,
        "reason_code": item.reason_code,
        "details": dict(item.details) if item.details else None,
    }


class SqliteEvaluationRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_snapshot_and_result(
        self, snapshot: EvaluationSnapshot, result: EvaluationResult
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_evaluation_snapshots(
                snapshot_id, tenant_id, subject_object_id, subject_revision,
                input_refs_json, created_at, policy_binding_id, authority_selection_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_id,
                snapshot.tenant_id,
                snapshot.subject_object_id,
                snapshot.subject_revision,
                json.dumps(dict(snapshot.input_refs), sort_keys=True),
                snapshot.created_at.isoformat(),
                snapshot.policy_binding_id,
                json.dumps(dict(snapshot.authority_selection or {}), sort_keys=True),
            ),
        )
        self._conn.execute(
            """
            INSERT INTO gov_evaluation_results(
                result_id, tenant_id, snapshot_id, evaluator_contract_version,
                outcome, reason_codes_json, created_at, primitive_results_json,
                policy_binding_id, evaluator_implementation_id, selected_authority_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.result_id,
                result.tenant_id,
                result.snapshot_id,
                result.evaluator_contract_version,
                result.outcome,
                json.dumps(list(result.reason_codes)),
                result.created_at.isoformat(),
                json.dumps(
                    [_primitive_to_dict(item) for item in result.primitive_results],
                    sort_keys=True,
                ),
                result.policy_binding_id,
                result.evaluator_implementation_id,
                json.dumps(dict(result.selected_authority or {}), sort_keys=True),
            ),
        )

    def load_result(self, tenant_id: str, result_id: str) -> EvaluationResult | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_evaluation_results
            WHERE tenant_id = ? AND result_id = ?
            """,
            (tenant_id, result_id),
        ).fetchone()
        if row is None:
            return None
        keys = set(row.keys())
        primitives_raw = []
        if "primitive_results_json" in keys and row["primitive_results_json"]:
            primitives_raw = json.loads(str(row["primitive_results_json"]))
        primitives = tuple(
            PrimitiveResult(
                primitive_id=str(item["primitive_id"]),
                outcome=PrimitiveOutcome(str(item["outcome"])),
                reason_code=str(item["reason_code"]),
                details=item.get("details"),
            )
            for item in primitives_raw
        )
        selected = None
        if "selected_authority_json" in keys and row["selected_authority_json"]:
            selected = dict(json.loads(str(row["selected_authority_json"])))
        return EvaluationResult(
            result_id=str(row["result_id"]),
            tenant_id=str(row["tenant_id"]),
            snapshot_id=str(row["snapshot_id"]),
            evaluator_contract_version=str(row["evaluator_contract_version"]),
            outcome=str(row["outcome"]),
            reason_codes=tuple(json.loads(str(row["reason_codes_json"]))),
            primitive_results=primitives,
            created_at=datetime.fromisoformat(str(row["created_at"])),
            policy_binding_id=(
                str(row["policy_binding_id"])
                if "policy_binding_id" in keys and row["policy_binding_id"]
                else None
            ),
            evaluator_implementation_id=(
                str(row["evaluator_implementation_id"])
                if "evaluator_implementation_id" in keys
                and row["evaluator_implementation_id"]
                else "m1.TaskTransitionEvaluator.impl.v1"
            ),
            selected_authority=selected,
        )
