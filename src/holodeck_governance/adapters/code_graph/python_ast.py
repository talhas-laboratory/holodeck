"""Python standard-library AST extractor adapter (selected M2 provider).

M2-020 ships the port-shaped adapter and capability declaration. Full fixture
extraction lands in M2-022. This module must not import non-stdlib parsing
providers.
"""

from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

from holodeck_governance.application.repository_extractor import (
    ExtractionCoverage,
    ExtractionRequest,
    ExtractionResult,
    ExtractorCapabilities,
    ProviderDescriptor,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeGraphReason,
    CoverageStatus,
    EntityKind,
    ExtractionDiagnostic,
    RelationKind,
    code_graph_error,
)

PYTHON_AST_PROVIDER_KEY = "python_stdlib_ast"
PYTHON_AST_PROVIDER_SCHEMA = "m2.python_stdlib_ast.v1"
PYTHON_AST_PROVIDER_VERSION = f"python:{sys.version_info.major}.{sys.version_info.minor}"


def _configuration_hash() -> str:
    payload = f"{PYTHON_AST_PROVIDER_KEY}|{PYTHON_AST_PROVIDER_SCHEMA}|{ast.__name__}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


_PROVIDER = ProviderDescriptor(
    provider_key=PYTHON_AST_PROVIDER_KEY,
    provider_version=PYTHON_AST_PROVIDER_VERSION,
    provider_schema_version=PYTHON_AST_PROVIDER_SCHEMA,
    configuration_hash=_configuration_hash(),
)


class PythonStdlibAstExtractor:
    """Selected M2 production-compatible extractor adapter.

    M2-020 proves the port and offline/stdlib constraints. Candidate emission
    for the golden fixture is implemented in M2-022.
    """

    def describe_capabilities(self) -> ExtractorCapabilities:
        return ExtractorCapabilities(
            provider=_PROVIDER,
            languages=("python",),
            entity_kinds=tuple(
                kind.value
                for kind in (
                    EntityKind.MODULE,
                    EntityKind.CLASS,
                    EntityKind.FUNCTION,
                    EntityKind.METHOD,
                    EntityKind.FILE,
                )
            ),
            relation_kinds=tuple(
                kind.value
                for kind in (
                    RelationKind.DEFINES,
                    RelationKind.IMPORTS,
                    RelationKind.CALLS,
                    RelationKind.INHERITS,
                    RelationKind.CONTAINS,
                )
            ),
            supports_incremental=True,
            supports_offline=True,
            notes=(
                "stdlib ast only; no Tree-sitter/GitNexus/Joern dependency",
                "full golden-fixture extraction arrives in M2-022",
            ),
        )

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        root = request.repository_path
        if not root.exists() or not root.is_dir():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "repository_path must be an existing directory",
            )
        if "python" not in request.language_allowlist:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "python_stdlib_ast requires python in language_allowlist",
            )
        py_files = sorted(root.rglob("*.py"))
        if request.limits.max_files is not None:
            py_files = py_files[: request.limits.max_files]
        # Touch stdlib ast so the selected adapter path is exercised without
        # claiming complete factual coverage before M2-022.
        parsed = 0
        diagnostics: list[ExtractionDiagnostic] = []
        for path in py_files:
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                parsed += 1
            except SyntaxError as exc:
                relative = _relative_or_name(root, path)
                diagnostics.append(
                    ExtractionDiagnostic(
                        code="python_syntax_error",
                        message=str(exc).strip() or "syntax error",
                        repository_relative_path=relative,
                    )
                )
        diagnostics.append(
            ExtractionDiagnostic(
                code="extractor_deferred",
                message=(
                    "PythonStdlibAstExtractor validates checkout parsing in M2-020; "
                    "normalized candidate emission is M2-022"
                ),
                repository_relative_path=None,
            )
        )
        return ExtractionResult(
            actual_revision=request.requested_revision,
            provider=_PROVIDER,
            candidate_entities=(),
            candidate_relations=(),
            diagnostics=tuple(diagnostics),
            coverage=ExtractionCoverage(
                status=CoverageStatus.PARTIAL,
                notes=(
                    f"parsed {parsed} python files; candidate emission deferred to M2-022",
                ),
            ),
        )


def _relative_or_name(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
