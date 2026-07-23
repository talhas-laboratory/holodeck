from __future__ import annotations

import json
import re
from http import HTTPStatus
from typing import IO, Any

from holodeck_control_plane.errors import (
    ConflictError,
    ContentionError,
    HolodeckError,
    NotFoundError,
    ValidationError,
)
from holodeck_control_plane.ids import validate_identifier

MAX_BODY_BYTES = 65_536
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class BadRequestError(HolodeckError):
    """Malformed HTTP request."""


class PayloadTooLargeError(HolodeckError):
    """Request body exceeds the allowed size."""


class UnsupportedMediaTypeError(HolodeckError):
    """Request Content-Type is not supported."""


def validate_bind_host(host: str, *, insecure_bind: bool) -> str:
    normalized = host.strip().lower()
    if normalized in LOOPBACK_HOSTS:
        return host.strip()
    if insecure_bind:
        return host.strip()
    raise SystemExit(
        f"refusing non-loopback bind on {host!r}; pass --insecure-bind to expose the API beyond loopback"
    )


def _content_type_is_json(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json"


def read_json_object(headers: Any, body: IO[bytes]) -> dict[str, Any]:
    if not _content_type_is_json(str(headers.get("Content-Type", ""))):
        raise UnsupportedMediaTypeError("Content-Type must be application/json")

    raw_length = str(headers.get("Content-Length", "")).strip()
    if not raw_length:
        raise BadRequestError("Content-Length is required")
    try:
        length = int(raw_length)
    except ValueError as error:
        raise BadRequestError("Content-Length must be an integer") from error
    if length < 0:
        raise BadRequestError("Content-Length must be non-negative")
    if length > MAX_BODY_BYTES:
        raise PayloadTooLargeError(f"request body exceeds {MAX_BODY_BYTES} bytes")

    raw = body.read(length)
    if len(raw) != length:
        raise BadRequestError("request body shorter than Content-Length")

    try:
        payload = json.loads(raw.decode("utf-8") if raw else "{}")
    except json.JSONDecodeError as error:
        raise BadRequestError("invalid JSON body") from error
    if not isinstance(payload, dict):
        raise BadRequestError("JSON body must be an object")
    return payload


def http_status_for_error(error: Exception) -> HTTPStatus:
    if isinstance(error, NotFoundError):
        return HTTPStatus.NOT_FOUND
    if isinstance(error, ConflictError):
        return HTTPStatus.CONFLICT
    if isinstance(error, ValidationError):
        return HTTPStatus.UNPROCESSABLE_ENTITY
    if isinstance(error, ContentionError):
        return HTTPStatus.SERVICE_UNAVAILABLE
    if isinstance(error, PayloadTooLargeError):
        return HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    if isinstance(error, UnsupportedMediaTypeError):
        return HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    if isinstance(error, (BadRequestError, json.JSONDecodeError, ValueError)):
        return HTTPStatus.BAD_REQUEST
    if isinstance(error, HolodeckError):
        return HTTPStatus.BAD_REQUEST
    return HTTPStatus.INTERNAL_SERVER_ERROR
