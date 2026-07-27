"""Command-scoped decision reconstruction (M1-022 / GS-013)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReconstructedDecision:
    receipt: dict[str, Any]
    evaluation_result: dict[str, Any] | None
    evaluation_snapshot: dict[str, Any] | None
    events: tuple[dict[str, Any], ...]
    transitions: tuple[dict[str, Any], ...]
    outbox_items: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    evidence_refs: tuple[dict[str, Any], ...]
    policy_bindings: tuple[dict[str, Any], ...]
    grants: tuple[dict[str, Any], ...]
    decisions: tuple[dict[str, Any], ...]


def reconstruct_from_command(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    command_id: str,
) -> ReconstructedDecision:
    receipt_row = conn.execute(
        """
        SELECT * FROM gov_command_receipts
        WHERE tenant_id = ? AND command_id = ?
        """,
        (tenant_id, command_id),
    ).fetchone()
    if receipt_row is None:
        raise LookupError(f"no receipt for command {command_id}")
    receipt = dict(receipt_row)

    evaluation_result = None
    evaluation_snapshot = None
    result_id = receipt.get("evaluation_result_id")
    if result_id:
        result_row = conn.execute(
            """
            SELECT * FROM gov_evaluation_results
            WHERE tenant_id = ? AND result_id = ?
            """,
            (tenant_id, result_id),
        ).fetchone()
        if result_row is not None:
            evaluation_result = dict(result_row)
            snap_row = conn.execute(
                """
                SELECT * FROM gov_evaluation_snapshots
                WHERE tenant_id = ? AND snapshot_id = ?
                """,
                (tenant_id, evaluation_result["snapshot_id"]),
            ).fetchone()
            if snap_row is not None:
                evaluation_snapshot = dict(snap_row)

    events = tuple(
        dict(row)
        for row in conn.execute(
            """
            SELECT * FROM gov_domain_events
            WHERE tenant_id = ? AND causation_id = ?
            ORDER BY ledger_sequence
            """,
            (tenant_id, command_id),
        ).fetchall()
    )

    transitions = tuple(
        dict(row)
        for row in conn.execute(
            """
            SELECT * FROM gov_transition_records
            WHERE tenant_id = ? AND command_id = ?
            ORDER BY created_at
            """,
            (tenant_id, command_id),
        ).fetchall()
    )

    outbox = tuple(
        dict(row)
        for row in conn.execute(
            """
            SELECT o.* FROM gov_outbox_items o
            JOIN gov_domain_events e ON e.event_id = o.domain_event_id
            WHERE o.tenant_id = ? AND e.causation_id = ?
            """,
            (tenant_id, command_id),
        ).fetchall()
    )

    subject_object_id = None
    subject_revision = None
    if evaluation_snapshot is not None:
        subject_object_id = evaluation_snapshot.get("subject_object_id")
        subject_revision = evaluation_snapshot.get("subject_revision")
    if subject_object_id is None and transitions:
        subject_object_id = transitions[0].get("subject_object_id")

    linked_ids = {
        str(row["linked_id"]): str(row["link_kind"])
        for row in _optional_rows(
            conn,
            """
            SELECT link_kind, linked_id FROM gov_command_subject_links
            WHERE tenant_id = ? AND command_id = ?
            """,
            (tenant_id, command_id),
        )
    }

    decisions = _optional_rows(
        conn,
        """
        SELECT * FROM gov_decisions
        WHERE tenant_id = ? AND command_id = ?
        ORDER BY created_at
        """,
        (tenant_id, command_id),
    )
    if not decisions:
        decision_object_ids = [
            linked_id
            for linked_id, kind in linked_ids.items()
            if kind == "decision"
        ]
        if decision_object_ids:
            placeholders = ",".join("?" for _ in decision_object_ids)
            decisions = _optional_rows(
                conn,
                f"""
                SELECT * FROM gov_decisions
                WHERE tenant_id = ? AND object_id IN ({placeholders})
                ORDER BY created_at
                """,
                (tenant_id, *decision_object_ids),
            )

    edges = ()
    evidence_refs = ()
    policy_bindings = ()
    grants = ()
    if subject_object_id is not None:
        edges = _optional_rows(
            conn,
            """
            SELECT * FROM gov_traceability_edges
            WHERE tenant_id = ?
              AND (from_object_id = ? OR to_object_id = ?)
            ORDER BY created_at
            """,
            (tenant_id, subject_object_id, subject_object_id),
        )
        evidence_refs = _optional_rows(
            conn,
            """
            SELECT * FROM gov_external_references
            WHERE tenant_id = ? AND subject_object_id = ?
            ORDER BY created_at
            """,
            (tenant_id, subject_object_id),
        )
        grants = _optional_rows(
            conn,
            """
            SELECT * FROM gov_delegated_grants
            WHERE tenant_id = ? AND subject_object_id = ?
            ORDER BY created_at
            """,
            (tenant_id, subject_object_id),
        )
        policy_bindings = _optional_rows(
            conn,
            """
            SELECT * FROM gov_policy_bindings
            WHERE tenant_id = ?
            ORDER BY precedence
            """,
            (tenant_id,),
        )
        if evaluation_snapshot is not None and evaluation_snapshot.get("policy_binding_id"):
            binding_id = str(evaluation_snapshot["policy_binding_id"])
            matched = tuple(
                b for b in policy_bindings if str(b.get("binding_id")) == binding_id
            )
            if matched:
                policy_bindings = matched
        if subject_revision is not None:
            grants = tuple(
                g
                for g in grants
                if int(g.get("subject_revision") or 0) == int(subject_revision)
            )

    return ReconstructedDecision(
        receipt=receipt,
        evaluation_result=evaluation_result,
        evaluation_snapshot=evaluation_snapshot,
        events=events,
        transitions=transitions,
        outbox_items=outbox,
        edges=edges,
        evidence_refs=evidence_refs,
        policy_bindings=policy_bindings,
        grants=grants,
        decisions=decisions,
    )


def receipt_reason_codes(receipt: dict[str, Any]) -> list[str]:
    raw = receipt.get("reason_codes_json") or "[]"
    return list(json.loads(str(raw)))


def _optional_rows(
    conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]
) -> tuple[dict[str, Any], ...]:
    try:
        return tuple(dict(row) for row in conn.execute(sql, params).fetchall())
    except sqlite3.Error:
        return ()
