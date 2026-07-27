"""Immutable command receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    receipt_id: str
    command_id: str
    tenant_id: str
    outcome: str
    reason_codes: tuple[str, ...]
    error_code: str | None
    created_at: datetime
    evaluation_result_id: str | None = None
    schema_version: str = "m1.command_receipt.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("receipt_id", self.receipt_id),
            ("command_id", self.command_id),
            ("tenant_id", self.tenant_id),
        ):
            require_opaque_id(value, name)
        if self.outcome not in {"accepted", "rejected"}:
            raise MalformedCommandError("receipt outcome must be accepted or rejected")
        if self.created_at.tzinfo is None:
            raise MalformedCommandError("created_at must be timezone-aware UTC")
