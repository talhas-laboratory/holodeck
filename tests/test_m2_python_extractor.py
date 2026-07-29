"""M2-022 Python stdlib AST extractor against the golden fixture."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from holodeck_governance.adapters.code_graph.python_ast import (
    PythonStdlibAstExtractor,
    deterministic_uuidv7,
)
from holodeck_governance.application.repository_extractor import ExtractionRequest
from holodeck_governance.application.repository_extractor_conformance import (
    run_extractor_conformance,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    UNRESOLVED_DYNAMIC_CALL,
    CodeGraphReason,
    EntityKind,
    ExtractionLimits,
    RelationKind,
)

ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_PARENT = ROOT / "tests" / "fixtures" / "code_graph"
if str(_FIXTURE_PARENT) not in sys.path:
    sys.path.insert(0, str(_FIXTURE_PARENT))

from python_reference import TREES_ROOT, fixture_revision_id  # noqa: E402
from python_reference.golden import (  # noqa: E402
    golden_entities_rev_a,
    golden_relations_rev_a,
)

TENANT = "01900000-0000-7000-8000-00000000a001"
WORKSPACE = "01900000-0000-7000-8000-00000000a002"
BINDING = "01900000-0000-7000-8000-00000000a003"


def _request(**overrides: object) -> ExtractionRequest:
    payload = {
        "repository_path": TREES_ROOT / "rev_a",
        "tenant_id": TENANT,
        "workspace_object_id": WORKSPACE,
        "repository_binding_id": BINDING,
        "requested_revision": fixture_revision_id("rev_a"),
        "limits": ExtractionLimits(
            max_files=200, max_entities=5000, max_relations=20000
        ),
    }
    payload.update(overrides)
    return ExtractionRequest(**payload)  # type: ignore[arg-type]


def _entity_identity(entity) -> tuple[str, str, str | None]:
    return (
        entity.entity_kind.value,
        entity.repository_relative_path,
        entity.qualified_name,
    )


def _relation_identity(
    relation, entities_by_id: dict[str, object]
) -> tuple[str, str, str]:
    source = entities_by_id[relation.source_entity_fact_id]
    target = entities_by_id[relation.target_entity_fact_id]
    return (
        relation.relation_kind.value,
        source.entity_key,  # type: ignore[attr-defined]
        target.entity_key,  # type: ignore[attr-defined]
    )


def _relation_identity_by_qn(
    relation, entities_by_id: dict[str, object]
) -> tuple[str, str, str | None]:
    source = entities_by_id[relation.source_entity_fact_id]
    target = entities_by_id[relation.target_entity_fact_id]
    # Path + target qualified name keeps CONFIGURES/READS stable when source
    # display names differ slightly from the curated golden sample.
    return (
        relation.relation_kind.value,
        source.repository_relative_path,  # type: ignore[attr-defined]
        getattr(target, "qualified_name", None),
    )


def test_deterministic_uuidv7_is_stable_and_versioned() -> None:
    first = deterministic_uuidv7("seed-a")
    second = deterministic_uuidv7("seed-a")
    assert first == second
    assert first[14] == "7"


def test_repeated_extraction_is_byte_stable() -> None:
    extractor = PythonStdlibAstExtractor()
    first = run_extractor_conformance(extractor, _request())
    second = run_extractor_conformance(extractor, _request())
    assert [e.entity_key for e in first.candidate_entities] == [
        e.entity_key for e in second.candidate_entities
    ]
    assert [r.relation_fact_id for r in first.candidate_relations] == [
        r.relation_fact_id for r in second.candidate_relations
    ]
    assert (
        first.actual_revision == second.actual_revision == fixture_revision_id("rev_a")
    )


def test_unresolved_dynamic_call_is_diagnostic_not_edge() -> None:
    result = run_extractor_conformance(PythonStdlibAstExtractor(), _request())
    assert any(item.code == UNRESOLVED_DYNAMIC_CALL for item in result.diagnostics)
    invoke = next(
        (
            entity
            for entity in result.candidate_entities
            if entity.qualified_name == "sample_app.service.Greeter.invoke"
        ),
        None,
    )
    assert invoke is not None
    assert all(
        not (
            relation.relation_kind is RelationKind.CALLS
            and relation.source_entity_fact_id == invoke.entity_fact_id
        )
        for relation in result.candidate_relations
    )


def test_golden_precision_recall_by_relation_kind() -> None:
    result = run_extractor_conformance(PythonStdlibAstExtractor(), _request())
    extracted_entities = {_entity_identity(e): e for e in result.candidate_entities}
    golden_entities = golden_entities_rev_a()
    golden_relations = golden_relations_rev_a(golden_entities)

    # Structural entity kinds should have solid recall on the fixture.
    for kind in (
        EntityKind.MODULE,
        EntityKind.CLASS,
        EntityKind.METHOD,
        EntityKind.FUNCTION,
        EntityKind.TEST,
        EntityKind.SCHEMA_OBJECT,
        EntityKind.API_ENTRY_POINT,
        EntityKind.MIGRATION,
    ):
        golden_ids = {
            _entity_identity(e) for e in golden_entities if e.entity_kind is kind
        }
        extracted_ids = {
            identity
            for identity, entity in extracted_entities.items()
            if entity.entity_kind is kind
        }
        if not golden_ids:
            continue
        recall = len(golden_ids & extracted_ids) / len(golden_ids)
        assert recall >= 0.8, f"{kind.value} entity recall {recall:.2f}"

    extracted_by_id = {e.entity_fact_id: e for e in result.candidate_entities}
    golden_by_id = {e.entity_fact_id: e for e in golden_entities}
    # Compare relations on qualified-name endpoints so fact-id differences do not matter.
    extracted_rel = {
        _relation_identity_by_qn(r, extracted_by_id) for r in result.candidate_relations
    }
    golden_rel = {_relation_identity_by_qn(r, golden_by_id) for r in golden_relations}
    report: dict[str, dict[str, float]] = {}
    for kind in RelationKind:
        g = {item for item in golden_rel if item[0] == kind.value}
        e = {item for item in extracted_rel if item[0] == kind.value}
        if not g and not e:
            continue
        precision = len(g & e) / len(e) if e else 1.0
        recall = len(g & e) / len(g) if g else 1.0
        report[kind.value] = {"precision": precision, "recall": recall}
        # Core structural kinds must clear a useful bar on the reference fixture.
        if kind in {
            RelationKind.DEFINES,
            RelationKind.IMPORTS,
            RelationKind.INHERITS,
            RelationKind.TESTS,
            RelationKind.MIGRATES,
            RelationKind.EXPOSES,
            RelationKind.CONFIGURES,
            RelationKind.READS,
            RelationKind.WRITES,
        }:
            assert recall >= 0.5, f"{kind.value} recall {recall:.2f} report={report}"
            # DEFINES/IMPORTS are denser than the curated golden sample.
            if kind not in {RelationKind.DEFINES, RelationKind.IMPORTS}:
                assert precision >= 0.5, f"{kind.value} precision {precision:.2f}"
    # Persist report for packet evidence via stdout-friendly structure.
    assert report
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "m2-022-python-extractor-metrics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_file_limit_and_exclude_paths() -> None:
    extractor = PythonStdlibAstExtractor()
    limited = run_extractor_conformance(
        extractor,
        _request(limits=ExtractionLimits(max_files=2, max_entities=5000)),
    )
    assert any(item.code == "file_limit" for item in limited.diagnostics)
    excluded = run_extractor_conformance(
        extractor,
        _request(path_excludes=("tests/",)),
    )
    assert any(item.code == "path_excluded" for item in excluded.diagnostics)
    assert all(
        not (entity.repository_relative_path or "").startswith("tests/")
        for entity in excluded.candidate_entities
        if entity.entity_kind is EntityKind.TEST
    )


def test_git_checkout_must_be_clean_to_represent_head(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True,
    )
    (tmp_path / "tracked.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)
    revision = subprocess.check_output(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True
    ).strip()

    (tmp_path / "tracked.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "untracked.py").write_text("VALUE = 3\n", encoding="utf-8")

    with pytest.raises(MalformedCommandError, match="worktree is dirty"):
        PythonStdlibAstExtractor().extract(
            _request(repository_path=tmp_path, requested_revision=revision)
        )


def test_revision_mismatch_before_extraction() -> None:
    with pytest.raises(
        MalformedCommandError, match=CodeGraphReason.REVISION_MISMATCH.value
    ):
        PythonStdlibAstExtractor().extract(
            _request(requested_revision="fixture:deadbeefdeadbeef")
        )


def test_malformed_python_file_is_diagnostic(tmp_path: Path) -> None:
    from holodeck_governance.adapters.code_graph.revision import tree_content_hash

    (tmp_path / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    revision = f"fixture:{tree_content_hash(tmp_path)}"
    result = PythonStdlibAstExtractor().extract(
        ExtractionRequest(
            repository_path=tmp_path,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            requested_revision=revision,
            limits=ExtractionLimits(max_files=20, max_entities=100),
        )
    )
    assert any(item.code == "python_syntax_error" for item in result.diagnostics)


def test_plain_directory_rejects_caller_supplied_revision(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(
        MalformedCommandError, match=CodeGraphReason.REVISION_MISMATCH.value
    ):
        PythonStdlibAstExtractor().extract(
            ExtractionRequest(
                repository_path=tmp_path,
                tenant_id=TENANT,
                workspace_object_id=WORKSPACE,
                repository_binding_id=BINDING,
                requested_revision="abcdef1234567890",
                limits=ExtractionLimits(max_files=20, max_entities=100),
            )
        )


def test_git_worktree_revision_resolves(tmp_path: Path) -> None:
    import subprocess

    from holodeck_governance.adapters.code_graph.revision import resolve_actual_revision

    main = tmp_path / "main"
    worktree = tmp_path / "worktree"
    main.mkdir()
    subprocess.run(["git", "init"], cwd=main, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=main,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=main,
        check=True,
        capture_output=True,
    )
    (main / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "mod.py"], cwd=main, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=main,
        check=True,
        capture_output=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=main, text=True
    ).strip()
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "HEAD"],
        cwd=main,
        check=True,
        capture_output=True,
    )
    assert (worktree / ".git").is_file()
    assert resolve_actual_revision(worktree, head) == head
    result = PythonStdlibAstExtractor().extract(
        ExtractionRequest(
            repository_path=worktree,
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            requested_revision=head,
            limits=ExtractionLimits(max_files=20, max_entities=100),
        )
    )
    assert result.actual_revision == head
    assert any(e.entity_kind is EntityKind.FUNCTION for e in result.candidate_entities)
