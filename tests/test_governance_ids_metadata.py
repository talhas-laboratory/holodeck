"""Tests for opaque IDs and shared governance metadata (M1-004)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import generate_uuidv7, is_uuidv7, require_opaque_id
from holodeck_governance.domain.metadata import (
    GovernanceMetadata,
    RevisionedMetadata,
    validate_revisioned_metadata_dict,
    validate_shared_metadata_dict,
)


def test_uuidv7_format_and_uniqueness() -> None:
    clock = {"ms": 1_720_000_000_000}

    def next_ms() -> int:
        clock["ms"] += 1
        return clock["ms"]

    ids = [generate_uuidv7(clock_ms=next_ms, rand_bytes=lambda n: bytes(range(n))) for _ in range(20)]
    assert len(set(ids)) == 20
    assert all(is_uuidv7(value) for value in ids)
    # time-ordered for increasing clock
    assert ids == sorted(ids)


def test_require_opaque_id_rejects_non_uuidv7() -> None:
    with pytest.raises(MalformedCommandError):
        require_opaque_id("not-a-uuid")
    with pytest.raises(MalformedCommandError):
        require_opaque_id("00000000-0000-4000-8000-000000000000")  # v4


def test_shared_metadata_validates_identically() -> None:
    actor = generate_uuidv7(clock_ms=lambda: 1, rand_bytes=lambda n: b"\x01" * n)
    tenant = generate_uuidv7(clock_ms=lambda: 2, rand_bytes=lambda n: b"\x02" * n)
    record = generate_uuidv7(clock_ms=lambda: 3, rand_bytes=lambda n: b"\x03" * n)
    created_at = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    payload = {
        "id": record,
        "tenant_id": tenant,
        "schema_version": "m1.test.v1",
        "created_at": created_at,
        "created_by_actor_id": actor,
        "provenance_ref": None,
    }
    validate_shared_metadata_dict(payload)
    meta = GovernanceMetadata(**{k: payload[k] for k in (
        "id", "tenant_id", "schema_version", "created_at", "created_by_actor_id", "provenance_ref"
    )})
    assert meta.tenant_id == tenant


def test_revisioned_metadata_requires_hash_and_monotonic_supersession() -> None:
    actor = generate_uuidv7(clock_ms=lambda: 1, rand_bytes=lambda n: b"\x11" * n)
    tenant = generate_uuidv7(clock_ms=lambda: 2, rand_bytes=lambda n: b"\x12" * n)
    object_id = generate_uuidv7(clock_ms=lambda: 3, rand_bytes=lambda n: b"\x13" * n)
    record = generate_uuidv7(clock_ms=lambda: 4, rand_bytes=lambda n: b"\x14" * n)
    created_at = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    payload = {
        "id": record,
        "tenant_id": tenant,
        "schema_version": "m1.test.v1",
        "created_at": created_at,
        "created_by_actor_id": actor,
        "object_id": object_id,
        "revision": 2,
        "supersedes_revision": 1,
        "content_hash": "sha256:abc",
    }
    validate_revisioned_metadata_dict(payload)
    with pytest.raises(MalformedCommandError):
        RevisionedMetadata(
            id=record,
            tenant_id=tenant,
            schema_version="m1.test.v1",
            created_at=created_at,
            created_by_actor_id=actor,
            object_id=object_id,
            revision=1,
            supersedes_revision=1,
            content_hash="sha256:abc",
        )
