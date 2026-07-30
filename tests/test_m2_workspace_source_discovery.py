"""M2-014 repository/source discovery and conservative trust classification."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from holodeck_governance.application.workspace_intelligence import (
    WorkspaceIntelligenceApplicationService,
)
from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.assignments import RoleAssignment
from holodeck_governance.domain.authority.roles import RoleProfile
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    MalformedCommandError,
    MissingAuthorityError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    ObservedSourcePath,
    SourceType,
    TrustClass,
    classify_observed_path,
    invent_sources_from_observations,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.intelligence import (
    SqliteWorkspaceIntelligenceRepository,
)
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant
from holodeck_governance.testing import FIXED_CLOCK, FixtureIds

NOW = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)


def _grant_curate(conn: sqlite3.Connection, ids: FixtureIds, *, actor_id: str) -> None:
    auth = SqliteAuthorityRepository(conn)
    revisions = SqliteRevisionRepository(conn)
    role_object_id = generate_uuidv7()
    revisions.register_object(
        GovernanceObject(
            object_id=role_object_id,
            tenant_id=ids.tenant_alpha,
            object_type="RoleProfile",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_role_profile(
        RoleProfile(
            role_profile_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            role_object_id=role_object_id,
            revision=1,
            name="intelligence-curator",
            permissions=(INTELLIGENCE_CURATE_PERMISSION,),
            jurisdiction={"tenant": ids.tenant_alpha},
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    auth.save_assignment(
        RoleAssignment(
            assignment_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            actor_id=actor_id,
            role_object_id=role_object_id,
            role_revision=1,
            workspace_object_id=None,
            jurisdiction_key="tenant",
            jurisdiction_value=ids.tenant_alpha,
            effective_from=NOW - timedelta(hours=1),
            created_at=NOW,
            created_by_actor_id=ids.system_service,
            effective_until=NOW + timedelta(days=30),
        )
    )


def _service() -> tuple[
    sqlite3.Connection, WorkspaceIntelligenceApplicationService, FixtureIds, str
]:
    ids = FixtureIds()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_governance(conn)
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'beta', 'Beta', 'm1.tenant.v1', ?, ?, NULL, 'active', 0)
        """,
        (ids.tenant_beta, NOW.isoformat(), ids.system_service),
    )
    auth = SqliteAuthorityRepository(conn)
    unauthorized = generate_uuidv7()
    for actor_id, tenant_id, name, kind in (
        (ids.human_owner, ids.tenant_alpha, "Owner", ActorKind.HUMAN),
        (ids.system_service, ids.tenant_alpha, "System", ActorKind.SERVICE),
        (unauthorized, ids.tenant_alpha, "NoAuth", ActorKind.HUMAN),
        (ids.human_reviewer, ids.tenant_beta, "Beta", ActorKind.HUMAN),
    ):
        auth.save_actor(
            Actor(
                actor_id=actor_id,
                tenant_id=tenant_id,
                kind=kind,
                display_name=name,
                created_at=FIXED_CLOCK,
                created_by_actor_id=ids.system_service,
            )
        )
    revisions = SqliteRevisionRepository(conn)
    revisions.register_object(
        GovernanceObject(
            object_id=ids.workspace_alpha_1,
            tenant_id=ids.tenant_alpha,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    revisions.register_object(
        GovernanceObject(
            object_id=ids.workspace_beta_1,
            tenant_id=ids.tenant_beta,
            object_type="Workspace",
            created_at=NOW,
            created_by_actor_id=ids.system_service,
        )
    )
    _grant_curate(conn, ids, actor_id=ids.human_owner)
    service = WorkspaceIntelligenceApplicationService(
        repository=SqliteWorkspaceIntelligenceRepository(conn)
    )
    return conn, service, ids, unauthorized


def test_classify_path_heuristics() -> None:
    cases = (
        (
            "repo://README.md",
            None,
            SourceType.DOCUMENT,
            TrustClass.ORDINARY_REFERENCE,
        ),
        (
            "docs/architecture.md",
            None,
            SourceType.DOCUMENT,
            TrustClass.ORDINARY_REFERENCE,
        ),
        (
            ".github/workflows/ci.yml",
            None,
            SourceType.REPOSITORY_FILE,
            TrustClass.TRUSTED_OBSERVATION,
        ),
        (
            "ci/pipeline.yaml",
            "ci",
            SourceType.REPOSITORY_FILE,
            TrustClass.TRUSTED_OBSERVATION,
        ),
        (
            "tests/test_discovery.py",
            None,
            SourceType.TEST_RESULT,
            TrustClass.ORDINARY_REFERENCE,
        ),
        (
            "src/holodeck_governance/app.py",
            None,
            SourceType.REPOSITORY_FILE,
            TrustClass.UNTRUSTED_REFERENCE,
        ),
        (
            "pyproject.toml",
            None,
            SourceType.REPOSITORY_FILE,
            TrustClass.ORDINARY_REFERENCE,
        ),
        (
            "mystery.bin",
            None,
            SourceType.REPOSITORY_FILE,
            TrustClass.UNTRUSTED_REFERENCE,
        ),
    )
    for locator, hint, source_type, trust in cases:
        candidate = classify_observed_path(
            ObservedSourcePath(
                locator=locator,
                observed_revision="rev-1",
                kind_hint=hint,
            )
        )
        assert candidate.source_type is source_type, locator
        assert candidate.trust_class is trust, locator
        assert candidate.trust_class not in {
            TrustClass.INSTRUCTION_AUTHORITY,
            TrustClass.AUTHORITATIVE_REFERENCE,
            TrustClass.GENERATED_INTERPRETATION,
        }


def test_invent_dedupes_and_never_sets_instruction_authority() -> None:
    observations = (
        ObservedSourcePath(locator="repo://README.md", observed_revision="a"),
        ObservedSourcePath(locator="repo://README.md", observed_revision="b"),
        ObservedSourcePath(locator="src/main.py", observed_revision="a"),
    )
    candidates = invent_sources_from_observations(observations)
    assert len(candidates) == 2
    assert {c.locator for c in candidates} == {"repo://README.md", "src/main.py"}
    for candidate in candidates:
        # instruction_authority is not a field on candidates; trust stays below IA.
        assert candidate.trust_class is not TrustClass.INSTRUCTION_AUTHORITY


def test_discovered_candidate_rejects_instruction_authority() -> None:
    from holodeck_governance.domain.workspace.intelligence.discovery import (
        DiscoveredSourceCandidate,
    )

    with pytest.raises(MalformedCommandError):
        DiscoveredSourceCandidate(
            source_type=SourceType.DOCUMENT,
            locator="repo://POLICY.md",
            observed_revision="1",
            trust_class=TrustClass.INSTRUCTION_AUTHORITY,
        )


def test_discover_and_register_without_instruction_authority() -> None:
    conn, service, ids, _ = _service()
    result = service.discover_and_register_sources(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        observations=(
            ObservedSourcePath(locator="repo://README.md", observed_revision="abc"),
            ObservedSourcePath(
                locator="src/pkg/module.py",
                observed_revision="abc",
                content_hash="deadbeef",
            ),
            ObservedSourcePath(
                locator=".github/workflows/test.yml", observed_revision="abc"
            ),
        ),
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert result.registered_count == 3
    assert result.skipped_count == 0
    sources = service.list_sources(
        ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
    )
    assert len(sources) == 3
    by_locator = {s.locator: s for s in sources}
    assert by_locator["repo://README.md"].source_type is SourceType.DOCUMENT
    assert by_locator["repo://README.md"].trust_class is TrustClass.ORDINARY_REFERENCE
    assert by_locator["repo://README.md"].instruction_authority is False
    assert (
        by_locator["src/pkg/module.py"].trust_class is TrustClass.UNTRUSTED_REFERENCE
    )
    assert by_locator["src/pkg/module.py"].content_hash == "deadbeef"
    assert (
        by_locator[".github/workflows/test.yml"].trust_class
        is TrustClass.TRUSTED_OBSERVATION
    )
    for source in sources:
        assert source.instruction_authority is False
        assert source.trust_class is not TrustClass.INSTRUCTION_AUTHORITY
    mission_count = conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Mission'"
    ).fetchone()[0]
    run_count = conn.execute(
        "SELECT COUNT(*) FROM gov_objects WHERE object_type = 'Run'"
    ).fetchone()[0]
    assert mission_count == 0
    assert run_count == 0


def test_rediscovery_skips_existing_natural_key() -> None:
    _conn, service, ids, _ = _service()
    first = service.discover_and_register_sources(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        observations=(
            ObservedSourcePath(locator="repo://README.md", observed_revision="1"),
            ObservedSourcePath(locator="docs/guide.md", observed_revision="1"),
        ),
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert first.registered_count == 2
    second = service.discover_and_register_sources(
        tenant_id=ids.tenant_alpha,
        workspace_object_id=ids.workspace_alpha_1,
        observations=(
            ObservedSourcePath(locator="repo://README.md", observed_revision="2"),
            ObservedSourcePath(locator="docs/guide.md", observed_revision="2"),
            ObservedSourcePath(locator="tests/test_a.py", observed_revision="2"),
        ),
        actor_id=ids.human_owner,
        at=NOW,
    )
    assert second.registered_count == 1
    assert second.skipped_count == 2
    assert set(second.skipped_existing_source_ids) == set(first.registered_source_ids)
    sources = service.list_sources(
        ids.workspace_alpha_1, tenant_id=ids.tenant_alpha
    )
    assert len(sources) == 3
    readme = next(s for s in sources if s.locator == "repo://README.md")
    # Existing row is preserved (idempotent skip), not overwritten.
    assert readme.observed_revision == "1"


def test_curate_permission_required() -> None:
    _conn, service, ids, unauthorized = _service()
    with pytest.raises(MissingAuthorityError):
        service.discover_and_register_sources(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_alpha_1,
            observations=(
                ObservedSourcePath(locator="repo://README.md", observed_revision="1"),
            ),
            actor_id=unauthorized,
            at=NOW,
        )


def test_cross_tenant_workspace_denied() -> None:
    _conn, service, ids, _ = _service()
    with pytest.raises(CrossTenantAccessError):
        service.discover_and_register_sources(
            tenant_id=ids.tenant_alpha,
            workspace_object_id=ids.workspace_beta_1,
            observations=(
                ObservedSourcePath(locator="repo://README.md", observed_revision="1"),
            ),
            actor_id=ids.human_owner,
            at=NOW,
        )
