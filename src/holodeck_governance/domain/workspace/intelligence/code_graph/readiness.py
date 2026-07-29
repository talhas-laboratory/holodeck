"""Factual code-graph readiness dimension (separate from workspace readiness).

Never claims universal completeness — COMPLETE_FOR_SUPPORTED_SCOPE means the
active snapshot covers Holodeck's supported extractor scope only.
"""

from __future__ import annotations

from enum import StrEnum

from holodeck_governance.domain.workspace.intelligence.code_graph.snapshots import (
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    CoverageStatus,
)


class FactualGraphReadiness(StrEnum):
    """Readiness of the factual repository graph for one binding."""

    ABSENT = "absent"
    PARTIAL = "partial"
    COMPLETE_FOR_SUPPORTED_SCOPE = "complete_for_supported_scope"
    STALE = "stale"
    UNRESOLVED = "unresolved"


def evaluate_factual_graph_readiness(
    *,
    active_snapshot: RepositoryGraphSnapshot | None,
    active_run: RepositoryExtractionRun | None,
    binding_repository_revision: str | None = None,
) -> FactualGraphReadiness:
    """Pure readiness evaluation for an active graph snapshot.

    ``COMPLETE_FOR_SUPPORTED_SCOPE`` is returned for complete coverage whether
    or not unresolved diagnostics (e.g. unresolved_dynamic_call) are present —
    Holodeck never claims a universally complete model of the repository.
    """

    if active_snapshot is None:
        return FactualGraphReadiness.ABSENT

    if (
        binding_repository_revision is not None
        and binding_repository_revision != active_snapshot.repository_revision
    ):
        return FactualGraphReadiness.STALE

    if active_run is None:
        return FactualGraphReadiness.UNRESOLVED

    coverage = active_snapshot.coverage_status
    if coverage is CoverageStatus.PARTIAL or coverage is CoverageStatus.UNKNOWN:
        return FactualGraphReadiness.PARTIAL

    if coverage is CoverageStatus.COMPLETE:
        # Unresolved diagnostics do not lower this dimension below supported-scope
        # complete; they remain visible on the run diagnostics separately.
        return FactualGraphReadiness.COMPLETE_FOR_SUPPORTED_SCOPE

    return FactualGraphReadiness.UNRESOLVED
