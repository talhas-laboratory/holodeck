from __future__ import annotations

import re

from holodeck_control_plane.errors import ValidationError

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def validate_identifier(value: str, name: str) -> str:
    candidate = value.strip()
    if not IDENTIFIER_PATTERN.fullmatch(candidate):
        raise ValidationError(f"invalid {name}: {value!r}")
    return candidate


def validate_identifier_input(value: object, name: str) -> str:
    if value is None:
        raise ValidationError(f"{name} is required")
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string")
    return validate_identifier(value, name)
