"""M2-020 repository extractor port and provider assessment tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from holodeck_governance.adapters.code_graph.fake import FakePythonReferenceExtractor
from holodeck_governance.adapters.code_graph.python_ast import (
    PYTHON_AST_PROVIDER_KEY,
    PythonStdlibAstExtractor,
)
from holodeck_governance.application.repository_extractor import (
    ExtractionRequest,
    ExtractorCapabilities,
    ProviderDescriptor,
)
from holodeck_governance.application.repository_extractor_conformance import (
    assert_module_avoids_provider_imports,
    run_extractor_conformance,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeGraphReason,
    CoverageStatus,
    ExtractionLimits,
)

ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_PARENT = ROOT / "tests" / "fixtures" / "code_graph"
if str(_FIXTURE_PARENT) not in sys.path:
    sys.path.insert(0, str(_FIXTURE_PARENT))

from python_reference import FIXTURE_ROOT, TREES_ROOT, fixture_revision_id  # noqa: E402
from python_reference.golden import (  # noqa: E402
    golden_diagnostics_rev_a,
    golden_entities_rev_a,
    golden_relations_rev_a,
)

BINDING = "01900000-0000-7000-8000-00000000a003"
TENANT = "01900000-0000-7000-8000-00000000a001"
WORKSPACE = "01900000-0000-7000-8000-00000000a002"
ASSESSMENT = ROOT / "artifacts" / "m2-code-graph-provider-assessment.md"
FORBIDDEN_PROVIDER_IMPORTS = (
    "tree_sitter",
    "gitnexus",
    "joern",
    "ladybug",
)


def _limits() -> ExtractionLimits:
    return ExtractionLimits(max_files=200, max_entities=5000, max_relations=20000)


def _request(*, revision: str | None = None) -> ExtractionRequest:
    return ExtractionRequest(
        repository_path=TREES_ROOT / "rev_a",
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        repository_binding_id=BINDING,
        requested_revision=revision or fixture_revision_id("rev_a"),
        limits=_limits(),
    )


def test_request_requires_immutable_revision_and_limits() -> None:
    with pytest.raises(MalformedCommandError, match=CodeGraphReason.MUTABLE_REVISION.value):
        ExtractionRequest(
            repository_path=TREES_ROOT / "rev_a",
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            requested_revision="main",
            limits=_limits(),
        )
    with pytest.raises(MalformedCommandError, match=CodeGraphReason.QUERY_LIMIT.value):
        ExtractionRequest(
            repository_path=TREES_ROOT / "rev_a",
            tenant_id=TENANT,
            workspace_object_id=WORKSPACE,
            repository_binding_id=BINDING,
            requested_revision=fixture_revision_id("rev_a"),
            limits=ExtractionLimits(),
        )


def test_port_and_adapters_avoid_provider_sdks() -> None:
    paths = [
        ROOT
        / "src"
        / "holodeck_governance"
        / "application"
        / "repository_extractor.py",
        ROOT
        / "src"
        / "holodeck_governance"
        / "application"
        / "repository_extractor_conformance.py",
        ROOT
        / "src"
        / "holodeck_governance"
        / "adapters"
        / "code_graph"
        / "fake.py",
        ROOT
        / "src"
        / "holodeck_governance"
        / "adapters"
        / "code_graph"
        / "python_ast.py",
        ROOT
        / "src"
        / "holodeck_governance"
        / "domain"
        / "workspace"
        / "intelligence"
        / "code_graph",
    ]
    for path in paths:
        if path.is_dir():
            for child in path.rglob("*.py"):
                assert_module_avoids_provider_imports(
                    child, forbidden=FORBIDDEN_PROVIDER_IMPORTS
                )
        else:
            assert_module_avoids_provider_imports(
                path, forbidden=FORBIDDEN_PROVIDER_IMPORTS
            )


def test_fake_extractor_conformance_against_golden_fixture() -> None:
    entities = golden_entities_rev_a()
    relations = golden_relations_rev_a(entities)
    extractor = FakePythonReferenceExtractor(
        entities=entities,
        relations=relations,
        diagnostics=golden_diagnostics_rev_a(),
        expected_revision=fixture_revision_id("rev_a"),
    )
    result = run_extractor_conformance(extractor, _request())
    assert result.coverage.status is CoverageStatus.COMPLETE
    assert len(result.candidate_entities) == len(entities)
    assert len(result.candidate_relations) == len(relations)
    assert result.actual_revision == fixture_revision_id("rev_a")


def test_selected_python_ast_adapter_emits_candidates_and_dynamic_diagnostic() -> None:
    from holodeck_governance.domain.workspace.intelligence.code_graph import (
        UNRESOLVED_DYNAMIC_CALL,
    )

    extractor = PythonStdlibAstExtractor()
    caps = extractor.describe_capabilities()
    assert caps.provider.provider_key == PYTHON_AST_PROVIDER_KEY
    assert caps.supports_offline is True
    assert "python" in caps.languages
    result = run_extractor_conformance(extractor, _request())
    assert result.candidate_entities
    assert result.candidate_relations
    assert any(item.code == UNRESOLVED_DYNAMIC_CALL for item in result.diagnostics)
    assert result.actual_revision == fixture_revision_id("rev_a")


def test_assessment_artifact_records_license_and_selection() -> None:
    text = ASSESSMENT.read_text(encoding="utf-8")
    for needle in (
        "PolyForm Noncommercial",
        "https://github.com/nxpatterns/gitnexus/blob/main/LICENSE",
        "python_stdlib_ast",
        "Tree-sitter",
        "Joern",
        "M2-022",
        fixture_revision_id("rev_a"),
    ):
        assert needle in text
    assert "research-only" in text.lower() or "research only" in text.lower()


def test_revisions_manifest_still_pins_fixture_identity() -> None:
    payload = json.loads((FIXTURE_ROOT / "revisions.json").read_text(encoding="utf-8"))
    assert (
        payload["revisions"]["rev_a"]["repository_revision"]
        == fixture_revision_id("rev_a")
    )


def test_provider_descriptor_rejects_blank_fields() -> None:
    with pytest.raises(MalformedCommandError):
        ProviderDescriptor(
            provider_key="",
            provider_version="1",
            provider_schema_version="s",
            configuration_hash="h",
        )


def test_capabilities_require_languages_and_kinds() -> None:
    provider = ProviderDescriptor(
        provider_key="x",
        provider_version="1",
        provider_schema_version="s",
        configuration_hash="h",
    )
    with pytest.raises(MalformedCommandError):
        ExtractorCapabilities(
            provider=provider,
            languages=(),
            entity_kinds=("module",),
            relation_kinds=("imports",),
            supports_incremental=False,
            supports_offline=True,
        )
