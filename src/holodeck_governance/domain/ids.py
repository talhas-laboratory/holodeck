"""UUIDv7-compatible opaque ID generation for Python 3.11+.

Ordering is an implementation property only and must never be used as an
authorization input. No runtime dependency is required.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Callable

from holodeck_governance.domain.errors import MalformedCommandError

_Clock = Callable[[], int]


def generate_uuidv7(*, clock_ms: _Clock | None = None, rand_bytes: Callable[[int], bytes] | None = None) -> str:
    """Return a UUIDv7 string (8-4-4-4-12 hex) per RFC 9562 layout."""

    millis = (clock_ms or _default_clock_ms)()
    if millis < 0 or millis >= (1 << 48):
        raise MalformedCommandError("uuidv7 timestamp out of range")
    random_source = rand_bytes or os.urandom
    rand = random_source(10)
    # 48-bit unix-ts-ms | ver(4)=7 | rand_a(12) | var(2)=10 | rand_b(62)
    value = (millis & 0xFFFFFFFFFFFF) << 80
    value |= 0x7 << 76
    value |= (int.from_bytes(rand[:2], "big") & 0x0FFF) << 64
    value |= 0b10 << 62
    value |= int.from_bytes(rand[2:], "big") & ((1 << 62) - 1)
    return str(uuid.UUID(int=value))


def is_uuidv7(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 7 and (parsed.int >> 62) & 0b11 == 0b10


def require_opaque_id(value: object, name: str = "id") -> str:
    if not isinstance(value, str) or not value.strip():
        raise MalformedCommandError(f"{name} must be a non-empty string")
    candidate = value.strip()
    if not is_uuidv7(candidate):
        raise MalformedCommandError(f"{name} must be a UUIDv7 opaque id")
    return candidate


def _default_clock_ms() -> int:
    return time.time_ns() // 1_000_000
