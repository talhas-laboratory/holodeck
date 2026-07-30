"""Tenant bootstrap and isolation tests (M1-003 / GS-001)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from holodeck_governance.domain.catalogs import SCENARIO_CATALOG_EXPECTATIONS
from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.errors import CrossTenantAccessError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.tenant import assert_same_tenant, build_default_local_tenant
from holodeck_governance.storage.sqlite.tenants import (
    SqliteTenantRepository,
    ensure_default_local_tenant,
)
from holodeck_governance.testing import FixtureIds


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_fresh_database_bootstraps_exactly_one_default_tenant() -> None:
    conn = _conn()
    first = ensure_default_local_tenant(
        conn,
        tenant_id=FixtureIds().tenant_alpha,
        created_by_actor_id=FixtureIds().system_service,
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
    )
    second = ensure_default_local_tenant(conn)
    assert first.id == second.id
    assert first.is_default_local is True
    repo = SqliteTenantRepository(conn)
    assert repo.count() == 1
    assert repo.get_default_local() is not None


def test_upgrade_path_adds_default_tenant_without_duplicates() -> None:
    conn = _conn()
    ensure_default_local_tenant(
        conn,
        tenant_id=FixtureIds().tenant_alpha,
        created_by_actor_id=FixtureIds().system_service,
    )
    ensure_default_local_tenant(conn)
    ensure_default_local_tenant(conn)
    assert SqliteTenantRepository(conn).count() == 1


def test_cross_tenant_reference_fails_closed_gs001() -> None:
    expectation = SCENARIO_CATALOG_EXPECTATIONS["GS-001"]
    assert DomainErrorCode.CROSS_TENANT_ACCESS in expectation.primary_error_codes
    assert ReasonCode.DENY_TENANT_ISOLATION in expectation.primary_reason_codes
    with pytest.raises(CrossTenantAccessError) as excinfo:
        assert_same_tenant(
            actor_tenant_id=FixtureIds().tenant_alpha,
            record_tenant_id=FixtureIds().tenant_beta,
            context="workspace",
        )
    assert excinfo.value.code == DomainErrorCode.CROSS_TENANT_ACCESS


def test_same_tenant_reference_allowed() -> None:
    assert_same_tenant(
        actor_tenant_id=FixtureIds().tenant_alpha,
        record_tenant_id=FixtureIds().tenant_alpha,
        context="workspace",
    )


def test_second_default_tenant_rejected_by_unique_index() -> None:
    conn = _conn()
    ensure_default_local_tenant(
        conn,
        tenant_id=FixtureIds().tenant_alpha,
        created_by_actor_id=FixtureIds().system_service,
    )
    repo = SqliteTenantRepository(conn)
    other = build_default_local_tenant(
        tenant_id=generate_uuidv7(),
        created_by_actor_id=FixtureIds().system_service,
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
    )
    with pytest.raises(sqlite3.IntegrityError):
        repo.save(other)
        conn.commit()
