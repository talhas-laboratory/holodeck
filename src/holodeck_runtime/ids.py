from __future__ import annotations

import re

from holodeck_runtime.errors import ValidationError

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def validate_identifier(value: str, name: str) -> str:
    candidate = value.strip()
    if not IDENTIFIER_PATTERN.fullmatch(candidate):
        raise ValidationError(f"invalid {name}: {value!r}")
    return candidate
