"""Thin control-plane adapter: M1 mutations go through application governance seam."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping

from holodeck_control_plane.errors import ConflictError, NotFoundError, ValidationError
from holodeck_governance.composition import open_governance_app
from holodeck_governance.domain.commands.envelope import CommandEnvelope
from holodeck_governance.domain.commands.receipt import CommandReceipt
from holodeck_governance.domain.errors import (
    GovernanceError,
    IdempotencyConflictError,
    MalformedCommandError,
)


def governance_mutation_entrypoints() -> tuple[str, ...]:
    return ("holodeck_control_plane.governance_commands.submit_governance_command",)


def receipt_to_dict(receipt: CommandReceipt) -> dict[str, Any]:
    return {
        "receipt_id": receipt.receipt_id,
        "command_id": receipt.command_id,
        "tenant_id": receipt.tenant_id,
        "outcome": receipt.outcome,
        "reason_codes": list(receipt.reason_codes),
        "error_code": receipt.error_code,
        "created_at": receipt.created_at.isoformat(),
        "evaluation_result_id": receipt.evaluation_result_id,
        "schema_version": receipt.schema_version,
    }


def command_envelope_from_mapping(raw: Mapping[str, Any]) -> CommandEnvelope:
    try:
        issued_at = raw["issued_at"]
        if isinstance(issued_at, str):
            issued_at = datetime.fromisoformat(issued_at)
        payload = raw.get("payload") or {}
        if not isinstance(payload, Mapping):
            raise MalformedCommandError("payload must be an object")
        return CommandEnvelope(
            command_id=str(raw["command_id"]),
            command_type=str(raw["command_type"]),
            tenant_id=str(raw["tenant_id"]),
            actor_id=str(raw["actor_id"]),
            target_object_id=str(raw["target_object_id"]),
            expected_revision=(
                int(raw["expected_revision"])
                if raw.get("expected_revision") is not None
                else None
            ),
            idempotency_key=str(raw["idempotency_key"]),
            payload_schema_version=str(raw["payload_schema_version"]),
            correlation_id=str(raw["correlation_id"]),
            issued_at=issued_at,
            payload=dict(payload),
            role_assignment_id=(
                str(raw["role_assignment_id"])
                if raw.get("role_assignment_id") is not None
                else None
            ),
            grant_id=str(raw["grant_id"]) if raw.get("grant_id") is not None else None,
        )
    except KeyError as exc:
        raise MalformedCommandError(f"missing command field: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise MalformedCommandError(f"invalid command field: {exc}") from exc


def submit_governance_command(
    database: str,
    command: CommandEnvelope | Mapping[str, Any],
    *,
    now: datetime | None = None,
    bootstrap_actor_id: str | None = None,
) -> CommandReceipt:
    """Public adapter entry. Authorization facts are never accepted from callers."""

    envelope = (
        command
        if isinstance(command, CommandEnvelope)
        else command_envelope_from_mapping(command)
    )
    app = open_governance_app(database, bootstrap_actor_id=bootstrap_actor_id)
    try:
        return app.handle(envelope, now=now)
    except IdempotencyConflictError as exc:
        raise ConflictError(str(exc)) from exc
    except MalformedCommandError as exc:
        raise ValidationError(str(exc)) from exc
    except GovernanceError as exc:
        raise ValidationError(str(exc)) from exc


def reconstruct_governance_decision(
    database: str,
    *,
    tenant_id: str,
    command_id: str,
) -> dict[str, Any]:
    app = open_governance_app(database)
    try:
        reconstructed = app.reconstruct(tenant_id=tenant_id, command_id=command_id)
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    return {
        "receipt": dict(reconstructed.receipt),
        "evaluation_result": reconstructed.evaluation_result,
        "evaluation_snapshot": reconstructed.evaluation_snapshot,
        "events": list(reconstructed.events),
        "transitions": list(reconstructed.transitions),
        "outbox_items": list(reconstructed.outbox_items),
        "edges": list(reconstructed.edges),
        "evidence_refs": list(reconstructed.evidence_refs),
        "policy_bindings": list(reconstructed.policy_bindings),
        "grants": list(reconstructed.grants),
        "decisions": list(reconstructed.decisions),
    }


_FORBIDDEN_AUTHORITY_FIELDS = frozenset(
    {
        "actor_tenant_id",
        "current_task_state",
        "actual_revision",
        "actor_permitted",
        "approval_subject_revision",
        "grant_ok",
        "grant_deny_reason",
        "requires_exact_approval",
    }
)


def _collect_forbidden_fields(payload: Mapping[str, Any], *, path: str = "") -> list[str]:
    found: list[str] = []
    for key, value in payload.items():
        here = f"{path}.{key}" if path else str(key)
        if key in _FORBIDDEN_AUTHORITY_FIELDS:
            found.append(here)
        if isinstance(value, Mapping):
            found.extend(_collect_forbidden_fields(value, path=here))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    found.extend(
                        _collect_forbidden_fields(item, path=f"{here}[{index}]")
                    )
    return found


def submit_governance_command_request(
    database: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """HTTP/CLI request shape -> receipt dict.

    Rejects legacy caller-supplied authority fields if present (including nested).
    """

    present = sorted(_collect_forbidden_fields(payload))
    if present:
        raise ValidationError(
            "caller-supplied authority/state fields are not allowed: "
            + ", ".join(present)
        )
    command_raw = payload.get("command")
    if not isinstance(command_raw, Mapping):
        raise ValidationError("command object is required")
    receipt = submit_governance_command(database, command_raw)
    return {"receipt": receipt_to_dict(receipt)}


def load_governance_command_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValidationError("governance command JSON must be an object")
    return payload
