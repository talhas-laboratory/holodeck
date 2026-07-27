"""Immutable revision and head tests (M1-005 / GS-002)."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime

import pytest

from holodeck_governance.domain.catalogs import SCENARIO_CATALOG_EXPECTATIONS
from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.errors import RevisionImmutableError, StaleRevisionError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FixtureIds


def _repo() -> tuple[sqlite3.Connection, SqliteRevisionRepository]:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    ensure_default_local_tenant(
        conn,
        tenant_id=FixtureIds().tenant_alpha,
        created_by_actor_id=FixtureIds().system_service,
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
    )
    return conn, SqliteRevisionRepository(conn)


def test_finalized_revision_cannot_be_mutated_in_place_gs002() -> None:
    assert DomainErrorCode.REVISION_IMMUTABLE in SCENARIO_CATALOG_EXPECTATIONS[
        "GS-002"
    ].primary_error_codes
    conn, repo = _repo()
    obj = GovernanceObject(
        object_id=FixtureIds().mission_object,
        tenant_id=FixtureIds().tenant_alpha,
        object_type="Mission",
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=FixtureIds().human_owner,
    )
    first = repo.create_initial_revision(obj=obj, payload={"title": "v1"})
    conn.commit()
    with pytest.raises(RevisionImmutableError) as excinfo:
        repo.reject_in_place_mutation(first.object_id, first.revision)
    assert excinfo.value.code == DomainErrorCode.REVISION_IMMUTABLE


def test_correction_creates_linked_revision_and_advances_head() -> None:
    conn, repo = _repo()
    obj = GovernanceObject(
        object_id=FixtureIds().mission_object,
        tenant_id=FixtureIds().tenant_alpha,
        object_type="Mission",
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=FixtureIds().human_owner,
    )
    first = repo.create_initial_revision(obj=obj, payload={"title": "v1"})
    second = repo.append_correction(
        object_id=obj.object_id,
        tenant_id=obj.tenant_id,
        actor_id=FixtureIds().human_owner,
        created_at=datetime(2026, 7, 24, 12, 1, tzinfo=UTC),
        payload={"title": "v2"},
        expected_head_revision=1,
    )
    conn.commit()
    assert second.revision == 2
    assert second.supersedes_revision == 1
    head = repo.get_head(obj.object_id)
    assert head is not None
    assert head.head_revision == 2
    assert head.head_revision_id == second.revision_id
    assert repo.get_revision(obj.object_id, 1) == first or repo.get_revision(
        obj.object_id, 1
    ).content_hash == first.content_hash


def test_stale_expected_head_rejected() -> None:
    conn, repo = _repo()
    obj = GovernanceObject(
        object_id=FixtureIds().mission_object,
        tenant_id=FixtureIds().tenant_alpha,
        object_type="Mission",
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=FixtureIds().human_owner,
    )
    repo.create_initial_revision(obj=obj, payload={"title": "v1"})
    repo.append_correction(
        object_id=obj.object_id,
        tenant_id=obj.tenant_id,
        actor_id=FixtureIds().human_owner,
        created_at=datetime(2026, 7, 24, 12, 1, tzinfo=UTC),
        payload={"title": "v2"},
        expected_head_revision=1,
    )
    conn.commit()
    with pytest.raises(StaleRevisionError):
        repo.append_correction(
            object_id=obj.object_id,
            tenant_id=obj.tenant_id,
            actor_id=FixtureIds().human_owner,
            created_at=datetime(2026, 7, 24, 12, 2, tzinfo=UTC),
            payload={"title": "v3"},
            expected_head_revision=1,
        )


def test_concurrent_writers_cannot_allocate_same_revision(tmp_path) -> None:
    db_path = tmp_path / "revisions.db"
    bootstrap = sqlite3.connect(db_path)
    ensure_default_local_tenant(
        bootstrap,
        tenant_id=FixtureIds().tenant_alpha,
        created_by_actor_id=FixtureIds().system_service,
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
    )
    repo = SqliteRevisionRepository(bootstrap)
    obj = GovernanceObject(
        object_id=FixtureIds().mission_object,
        tenant_id=FixtureIds().tenant_alpha,
        object_type="Mission",
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=FixtureIds().human_owner,
    )
    repo.create_initial_revision(obj=obj, payload={"title": "v1"})
    bootstrap.commit()
    bootstrap.close()

    errors: list[BaseException] = []
    successes: list[int] = []

    def worker(seed: int) -> None:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        local = SqliteRevisionRepository(conn)
        try:
            conn.execute("BEGIN IMMEDIATE")
            revision = local.append_correction(
                object_id=FixtureIds().mission_object,
                tenant_id=FixtureIds().tenant_alpha,
                actor_id=FixtureIds().human_owner,
                created_at=datetime(2026, 7, 24, 12, 1, tzinfo=UTC),
                payload={"title": f"v-{seed}", "nonce": generate_uuidv7()},
                expected_head_revision=1,
            )
            conn.commit()
            successes.append(revision.revision)
        except Exception as exc:  # noqa: BLE001 - collect worker failures
            conn.rollback()
            errors.append(exc)
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=(idx,)) for idx in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert successes[0] == 2
    assert errors  # the loser fails unique(object_id, revision) or stale head
