"""Reusable repository-extractor conformance helpers (no provider SDK)."""

from __future__ import annotations

import ast
from pathlib import Path

from holodeck_governance.application.repository_extractor import (
    ExtractionRequest,
    ExtractionResult,
    RepositoryExtractor,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeGraphReason,
    CoverageStatus,
    assert_extraction_candidates_conform,
    code_graph_error,
)


def assert_extractor_capabilities_are_honest(extractor: RepositoryExtractor) -> None:
    caps = extractor.describe_capabilities()
    assert caps.provider.provider_key.strip()
    assert caps.provider.provider_version.strip()
    assert caps.languages
    assert caps.entity_kinds
    assert caps.relation_kinds


def assert_extraction_result_conforms(
    result: ExtractionResult, *, requested_revision: str
) -> None:
    if result.actual_revision != requested_revision:
        raise code_graph_error(
            CodeGraphReason.REVISION_MISMATCH,
            "actual_revision must equal requested_revision for activation eligibility",
        )
    assert_extraction_candidates_conform(
        entities=result.candidate_entities,
        relations=result.candidate_relations,
        diagnostics=result.diagnostics,
    )
    if result.coverage.status is CoverageStatus.UNKNOWN:
        raise code_graph_error(
            CodeGraphReason.PARTIAL_COVERAGE,
            "extraction results must not claim unknown coverage",
        )


def assert_module_avoids_provider_imports(path: Path, *, forbidden: tuple[str, ...]) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for needle in forbidden:
                    if needle in alias.name:
                        raise AssertionError(f"{path} imports {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            for needle in forbidden:
                if needle in node.module:
                    raise AssertionError(f"{path} imports {node.module}")


def run_extractor_conformance(
    extractor: RepositoryExtractor,
    request: ExtractionRequest,
) -> ExtractionResult:
    """Exercise the shared request/result gates against any adapter."""

    assert_extractor_capabilities_are_honest(extractor)
    result = extractor.extract(request)
    assert_extraction_result_conforms(
        result, requested_revision=request.requested_revision
    )
    return result
