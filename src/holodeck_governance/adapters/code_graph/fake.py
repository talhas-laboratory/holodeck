"""Deterministic fake repository extractor for conformance tests."""

from __future__ import annotations

from holodeck_governance.application.repository_extractor import (
    ExtractionCoverage,
    ExtractionRequest,
    ExtractionResult,
    ExtractorCapabilities,
    ProviderDescriptor,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeEntityFact,
    CodeGraphReason,
    CodeRelationFact,
    CoverageStatus,
    EntityKind,
    ExtractionDiagnostic,
    RelationKind,
    UNRESOLVED_DYNAMIC_CALL,
    assert_extraction_candidates_conform,
    code_graph_error,
)

FAKE_PROVIDER_KEY = "fake_python_reference"
FAKE_PROVIDER_VERSION = "1.0.0"
FAKE_PROVIDER_SCHEMA = "m2.fake_extractor.v1"
FAKE_CONFIGURATION_HASH = "fixture-golden-rev-a"

_PROVIDER = ProviderDescriptor(
    provider_key=FAKE_PROVIDER_KEY,
    provider_version=FAKE_PROVIDER_VERSION,
    provider_schema_version=FAKE_PROVIDER_SCHEMA,
    configuration_hash=FAKE_CONFIGURATION_HASH,
)


class FakePythonReferenceExtractor:
    """Returns precomputed golden facts for the python_reference fixture.

    Used by the provider conformance kit. Not a production extractor.
    """

    def __init__(
        self,
        *,
        entities: tuple[CodeEntityFact, ...],
        relations: tuple[CodeRelationFact, ...],
        diagnostics: tuple[ExtractionDiagnostic, ...] | None = None,
        expected_revision: str,
    ) -> None:
        self._entities = entities
        self._relations = relations
        self._diagnostics = diagnostics or (
            ExtractionDiagnostic(
                code=UNRESOLVED_DYNAMIC_CALL,
                message="dynamic call site left unresolved",
                repository_relative_path="sample_app/service.py",
            ),
        )
        self._expected_revision = expected_revision
        assert_extraction_candidates_conform(
            entities=self._entities,
            relations=self._relations,
            diagnostics=self._diagnostics,
        )

    def describe_capabilities(self) -> ExtractorCapabilities:
        return ExtractorCapabilities(
            provider=_PROVIDER,
            languages=("python",),
            entity_kinds=tuple(kind.value for kind in EntityKind),
            relation_kinds=tuple(kind.value for kind in RelationKind),
            supports_incremental=True,
            supports_offline=True,
            notes=("deterministic golden-fixture adapter for conformance",),
        )

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        if request.requested_revision != self._expected_revision:
            raise code_graph_error(
                CodeGraphReason.REVISION_MISMATCH,
                "fake extractor only serves its pinned fixture revision",
            )
        if not request.repository_path.exists():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "repository_path does not exist",
            )
        result = ExtractionResult(
            actual_revision=request.requested_revision,
            provider=_PROVIDER,
            candidate_entities=self._entities,
            candidate_relations=self._relations,
            diagnostics=self._diagnostics,
            coverage=ExtractionCoverage(
                status=CoverageStatus.COMPLETE,
                notes=("golden fixture facts",),
            ),
        )
        assert_extraction_candidates_conform(
            entities=result.candidate_entities,
            relations=result.candidate_relations,
            diagnostics=result.diagnostics,
        )
        return result
