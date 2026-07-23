from __future__ import annotations


class HolodeckError(Exception):
    """Base domain error for Holodeck runtime."""


class ContentionError(HolodeckError):
    """SQLite lock could not be acquired within the busy timeout."""


class ValidationError(HolodeckError):
    """Input or state transition is invalid."""


class ConflictError(HolodeckError):
    """Request conflicts with current coordination state."""


class NotFoundError(HolodeckError):
    """Requested record does not exist."""
