"""Shared helpers for typed work records."""

from __future__ import annotations

from datetime import datetime

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id


def require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None:
        raise MalformedCommandError(f"{name} must be timezone-aware UTC")


def require_ids(**values: str) -> None:
    for name, value in values.items():
        require_opaque_id(value, name)
