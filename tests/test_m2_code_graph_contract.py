"""M2-019 factual code-graph contract suite."""

from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CODE_GRAPH_SCHEMA_VERSION,
    ENTITY_KIND_CATALOG_VERSION,
    INITIAL_ENTITY_KINDS,
    INITIAL_RELATION_KINDS,
    RELATION_KIND_CATALOG_VERSION,
    UNRESOLVED_DYNAMIC_CALL,
    CodeEntityFact,
    CodeGraphReason,
    CodeRelationFact,
    CoverageStatus,
    EntityKind,
    ExtractionDiagnostic,
    ExtractionLimits,
    ExtractionRunStatus,
    ObservationMethod,
    RelationKind,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    SnapshotStatus,
    SourceSpan,
    assert_extraction_candidates_conform,
    assert_relation_endpoints_resolve,
    build_entity_key,
    build_relation_key,
    normalize_repository_relative_path,
    relation_kinds_covered,
    require_immutable_repository_revision,
)

ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_PARENT = ROOT / "tests" / "fixtures" / "code_graph"
if str(_FIXTURE_PARENT) not in sys.path:
    sys.path.insert(0, str(_FIXTURE_PARENT))

from python_reference import (  # noqa: E402
    FIXTURE_ROOT,
    TREES_ROOT,
    changed_paths,
    fixture_revision_id,
    tree_revision_hash,
    write_revisions_manifest,
)
from python_reference.golden import (  # noqa: E402
    DEFERRED_RELATION_KINDS_FROM_PYTHON_FIXTURE,
    golden_diagnostics_rev_a,
    golden_entities_rev_a,
    golden_paths_rev_a,
    golden_relations_rev_a,
)

CODE_GRAPH_DOMAIN = (
    ROOT
    / "src"
    / "holodeck_governance"
    / "domain"
    / "workspace"
    / "intelligence"
    / "code_graph"
)
DESIGN = ROOT / "docs" / "plans" / "2026-07-29-persistent-codebase-factual-graph-design.md"

TENANT = "01900000-0000-7000-8000-00000000a001"
WORKSPACE = "01900000-0000-7000-8000-00000000a002"
BINDING = "01900000-0000-7000-8000-00000000a003"
SOURCE = "01900000-0000-7000-8000-00000000a010"
OBS = "01900000-0000-7000-8000-00000000a011"
ACTOR = "01900000-0000-7000-8000-00000000a020"
SNAP = "01900000-0000-7000-8000-00000000a030"
RUN = "01900000-0000-7000-8000-00000000a031"
E1 = "01900000-0000-7000-8000-00000000b001"
E2 = "01900000-0000-7000-8000-00000000b002"
R1 = "01900000-0000-7000-8000-00000000c001"
NOW = datetime(2026, 7, 29, 14, 0, tzinfo=UTC)


def test_design_doc_names_required_graph_records() -> None:
    text = DESIGN.read_text(encoding="utf-8")
    for needle in (
        "RepositoryGraphSnapshot",
        "RepositoryExtractionRun",
        "CodeEntityFact",
        "CodeRelationFact",
        "observation_method",
        "tool_inferred",
    ):
        assert needle in text


def test_domain_package_has_no_storage_or_provider_imports() -> None:
    forbidden = ("sqlite3", "holodeck_governance.storage", "tree_sitter", "gitnexus")
    for path in CODE_GRAPH_DOMAIN.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for needle in forbidden:
                        assert needle not in alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                for needle in forbidden:
                    assert needle not in node.module


def test_catalogs_are_explicit_and_versioned() -> None:
    assert CODE_GRAPH_SCHEMA_VERSION.startswith("m2.code_graph.")
    assert ENTITY_KIND_CATALOG_VERSION.startswith("m2.code_entity_kind.")
    assert RELATION_KIND_CATALOG_VERSION.startswith("m2.code_relation_kind.")
    assert INITIAL_ENTITY_KINDS == frozenset(EntityKind)
    assert INITIAL_RELATION_KINDS == frozenset(RelationKind)
    assert EntityKind.MODULE in INITIAL_ENTITY_KINDS
    assert RelationKind.CALLS in INITIAL_RELATION_KINDS


def test_entity_key_is_deterministic_and_path_normalized() -> None:
    first = build_entity_key(
        entity_kind=EntityKind.FUNCTION,
        repository_relative_path="./sample_app/api.py",
        qualified_name="sample_app.api.create_app",
    )
    second = build_entity_key(
        entity_kind=EntityKind.FUNCTION,
        repository_relative_path="sample_app/api.py",
        qualified_name="sample_app.api.create_app",
    )
    assert first == second
    assert "sample_app/api.py" in first


def test_relation_key_is_deterministic() -> None:
    span = SourceSpan(start_line=2, end_line=2, start_column=1, end_column=8)
    first = build_relation_key(
        relation_kind=RelationKind.IMPORTS,
        source_entity_key="a",
        target_entity_key="b",
        evidence_path="sample_app/service.py",
        span=span,
    )
    second = build_relation_key(
        relation_kind=RelationKind.IMPORTS,
        source_entity_key="a",
        target_entity_key="b",
        evidence_path="sample_app/service.py",
        span=span,
    )
    assert first == second


@pytest.mark.parametrize(
    "path",
    ["/abs/path.py", "C:\\windows\\path.py", "../escape.py", ""],
)
def test_absolute_and_invalid_paths_rejected(path: str) -> None:
    with pytest.raises(MalformedCommandError, match="code_graph\\."):
        normalize_repository_relative_path(path)


@pytest.mark.parametrize("revision", ["main", "master", "HEAD", "refs/heads/main", ""])
def test_mutable_revisions_rejected(revision: str) -> None:
    with pytest.raises(
        MalformedCommandError,
        match=CodeGraphReason.MUTABLE_REVISION.value
        + "|"
        + CodeGraphReason.MALFORMED_FACT.value,
    ):
        require_immutable_repository_revision(revision)


def test_hex_and_fixture_revisions_accepted() -> None:
    assert require_immutable_repository_revision("abc1234") == "abc1234"
    assert (
        require_immutable_repository_revision("fixture:abcd1234")
        == "fixture:abcd1234"
    )


def test_invalid_spans_rejected() -> None:
    with pytest.raises(MalformedCommandError, match=CodeGraphReason.INVALID_SPAN.value):
        SourceSpan(start_line=0, end_line=1)
    with pytest.raises(MalformedCommandError, match=CodeGraphReason.INVALID_SPAN.value):
        SourceSpan(start_line=3, end_line=2)
    with pytest.raises(MalformedCommandError, match=CodeGraphReason.INVALID_SPAN.value):
        SourceSpan(start_line=1, end_line=1, start_column=1, end_column=None)


def _entity(
    *,
    entity_id: str = E1,
    kind: EntityKind = EntityKind.FUNCTION,
    path: str = "sample_app/api.py",
    qn: str | None = "sample_app.api.create_app",
    method: ObservationMethod = ObservationMethod.DIRECT_PARSE,
    native_id: str | None = None,
) -> CodeEntityFact:
    return CodeEntityFact(
        entity_fact_id=entity_id,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        repository_binding_id=BINDING,
        entity_key=build_entity_key(
            entity_kind=kind, repository_relative_path=path, qualified_name=qn
        ),
        entity_kind=kind,
        repository_relative_path=path,
        source_id=SOURCE,
        source_observation_id=OBS,
        observation_method=method,
        created_at=NOW,
        qualified_name=qn,
        extractor_native_id=native_id,
    )


def test_tool_inferred_entity_requires_native_id() -> None:
    with pytest.raises(
        MalformedCommandError,
        match=CodeGraphReason.INVALID_OBSERVATION_METHOD.value,
    ):
        _entity(method=ObservationMethod.TOOL_INFERRED, native_id=None)


def test_tool_inferred_relation_requires_confidence_and_diagnostic() -> None:
    source = _entity(entity_id=E1)
    target = _entity(
        entity_id=E2,
        kind=EntityKind.CLASS,
        path="sample_app/service.py",
        qn="sample_app.service.Greeter",
    )
    with pytest.raises(
        MalformedCommandError, match=CodeGraphReason.INVALID_CONFIDENCE.value
    ):
        CodeRelationFact(
            relation_fact_id=R1,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            relation_kind=RelationKind.CALLS,
            source_entity_fact_id=source.entity_fact_id,
            target_entity_fact_id=target.entity_fact_id,
            evidence_source_id=SOURCE,
            evidence_observation_id=OBS,
            observation_method=ObservationMethod.TOOL_INFERRED,
            created_at=NOW,
            confidence=None,
            diagnostic="guess",
        )
    with pytest.raises(
        MalformedCommandError,
        match=CodeGraphReason.INVALID_OBSERVATION_METHOD.value,
    ):
        CodeRelationFact(
            relation_fact_id=R1,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            relation_kind=RelationKind.CALLS,
            source_entity_fact_id=source.entity_fact_id,
            target_entity_fact_id=target.entity_fact_id,
            evidence_source_id=SOURCE,
            evidence_observation_id=OBS,
            observation_method=ObservationMethod.TOOL_INFERRED,
            created_at=NOW,
            confidence=0.5,
            diagnostic=None,
        )


def test_direct_relation_rejects_confidence() -> None:
    source = _entity(entity_id=E1)
    target = _entity(
        entity_id=E2,
        kind=EntityKind.CLASS,
        path="sample_app/service.py",
        qn="sample_app.service.Greeter",
    )
    with pytest.raises(
        MalformedCommandError, match=CodeGraphReason.INVALID_CONFIDENCE.value
    ):
        CodeRelationFact(
            relation_fact_id=R1,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            relation_kind=RelationKind.CALLS,
            source_entity_fact_id=source.entity_fact_id,
            target_entity_fact_id=target.entity_fact_id,
            evidence_source_id=SOURCE,
            evidence_observation_id=OBS,
            observation_method=ObservationMethod.DIRECT_PARSE,
            created_at=NOW,
            confidence=0.9,
        )


def test_dangling_relation_endpoints_rejected() -> None:
    source = _entity(entity_id=E1)
    relation = CodeRelationFact(
        relation_fact_id=R1,
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        repository_binding_id=BINDING,
        relation_kind=RelationKind.CALLS,
        source_entity_fact_id=source.entity_fact_id,
        target_entity_fact_id=E2,
        evidence_source_id=SOURCE,
        evidence_observation_id=OBS,
        observation_method=ObservationMethod.DIRECT_PARSE,
        created_at=NOW,
    )
    with pytest.raises(
        MalformedCommandError, match=CodeGraphReason.DANGLING_ENDPOINT.value
    ):
        assert_relation_endpoints_resolve(entities=(source,), relations=(relation,))


def test_extraction_run_rejects_revision_mismatch_on_success() -> None:
    with pytest.raises(
        MalformedCommandError, match=CodeGraphReason.REVISION_MISMATCH.value
    ):
        RepositoryExtractionRun(
            extraction_run_id=RUN,
            snapshot_id=SNAP,
            provider_key="python_ast",
            provider_version="1.0.0",
            provider_schema_version="m2.python_ast.v1",
            configuration_hash="abc",
            requested_revision="aaaaaaaa",
            actual_revision="bbbbbbbb",
            started_at=NOW,
            completed_at=NOW,
            status=ExtractionRunStatus.SUCCEEDED,
            created_by_actor_id=ACTOR,
            limits=ExtractionLimits(max_files=100),
        )


def test_active_snapshot_requires_activation_and_known_coverage() -> None:
    with pytest.raises(MalformedCommandError, match="activated_at"):
        RepositoryGraphSnapshot(
            snapshot_id=SNAP,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            repository_revision="fixture:abcd1234",
            status=SnapshotStatus.ACTIVE,
            extraction_run_id=RUN,
            coverage_status=CoverageStatus.COMPLETE,
            entity_count=1,
            relation_count=0,
            created_by_actor_id=ACTOR,
            created_at=NOW,
        )
    with pytest.raises(
        MalformedCommandError, match=CodeGraphReason.PARTIAL_COVERAGE.value
    ):
        RepositoryGraphSnapshot(
            snapshot_id=SNAP,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            repository_revision="fixture:abcd1234",
            status=SnapshotStatus.ACTIVE,
            extraction_run_id=RUN,
            coverage_status=CoverageStatus.UNKNOWN,
            entity_count=1,
            relation_count=0,
            created_by_actor_id=ACTOR,
            created_at=NOW,
            activated_at=NOW,
        )


def test_fixture_revisions_are_stable_content_identities() -> None:
    manifest = write_revisions_manifest()
    on_disk = json.loads(
        (FIXTURE_ROOT / "revisions.json").read_text(encoding="utf-8")
    )
    assert on_disk == manifest
    rev_a = manifest["revisions"]["rev_a"]["repository_revision"]
    rev_b = manifest["revisions"]["rev_b"]["repository_revision"]
    assert rev_a == fixture_revision_id("rev_a")
    assert rev_b == fixture_revision_id("rev_b")
    assert rev_a != rev_b
    assert rev_a.startswith("fixture:")
    assert tree_revision_hash(TREES_ROOT / "rev_a") in rev_a
    assert set(manifest["revisions"]["rev_b"]["changed_paths_from_rev_a"]) == set(
        changed_paths(TREES_ROOT / "rev_a", TREES_ROOT / "rev_b")
    )
    assert "sample_app/service.py" in manifest["revisions"]["rev_b"][
        "changed_paths_from_rev_a"
    ]


def test_golden_facts_cover_relation_catalog_or_mark_deferred() -> None:
    entities = golden_entities_rev_a()
    relations = golden_relations_rev_a(entities)
    diagnostics = golden_diagnostics_rev_a()
    assert_extraction_candidates_conform(
        entities=entities, relations=relations, diagnostics=diagnostics
    )
    covered = relation_kinds_covered(relations)
    missing = INITIAL_RELATION_KINDS - covered - DEFERRED_RELATION_KINDS_FROM_PYTHON_FIXTURE
    assert not missing
    assert DEFERRED_RELATION_KINDS_FROM_PYTHON_FIXTURE.isdisjoint(covered)


def test_unresolved_dynamic_call_is_diagnostic_not_edge() -> None:
    diagnostics = golden_diagnostics_rev_a()
    assert any(item.code == UNRESOLVED_DYNAMIC_CALL for item in diagnostics)
    assert all(
        isinstance(item, ExtractionDiagnostic) for item in diagnostics
    )
    relations = golden_relations_rev_a()
    invoke = next(
        entity
        for entity in golden_entities_rev_a()
        if entity.qualified_name == "sample_app.service.Greeter.invoke"
    )
    # No CALLS edge originates from the unresolved dynamic method.
    assert all(
        not (
            relation.relation_kind is RelationKind.CALLS
            and relation.source_entity_fact_id == invoke.entity_fact_id
        )
        for relation in relations
    )


def test_golden_paths_are_non_empty_evidence_chains() -> None:
    paths = golden_paths_rev_a()
    assert paths
    entities = {
        entity.qualified_name
        for entity in golden_entities_rev_a()
        if entity.qualified_name is not None
    }
    # File path used as terminal evidence may be a qualified_name on FILE entities.
    entities |= {
        entity.repository_relative_path for entity in golden_entities_rev_a()
    }
    for path in paths:
        assert len(path) >= 2
        for step in path:
            assert step in entities


def test_fixture_trees_contain_required_shapes() -> None:
    rev_a = TREES_ROOT / "rev_a"
    for relative in (
        "pyproject.toml",
        "config/settings.toml",
        "sample_app/service.py",
        "sample_app/api.py",
        "migrations/001_init.py",
        "tests/test_service.py",
        "data/items.json",
    ):
        assert (rev_a / relative).is_file()
    service = (rev_a / "sample_app/service.py").read_text(encoding="utf-8")
    assert "globals()[handler_name]" in service
