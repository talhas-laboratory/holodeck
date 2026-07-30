"""Explainable workspace discovery and eligibility evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from holodeck_governance.domain.collaboration.types import LocationKind
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.workspace.bindings import (
    CollaborationLocationBinding,
    RepositoryBinding,
    WorkspaceBindingStatus,
)

_LOCATION_SPECIFICITY: Mapping[LocationKind, int] = {
    LocationKind.THREAD: 30,
    LocationKind.CHANNEL: 20,
    LocationKind.PROJECT: 18,
    LocationKind.DM: 15,
    LocationKind.COMMUNITY: 10,
}

_INACTIVE_WORKSPACE_STATUSES = frozenset(
    {"suspended", "archived", "retired", "missing"}
)


class WorkspaceDiscoveryOutcome(StrEnum):
    SELECTED = "selected"
    AMBIGUOUS = "ambiguous"
    UNBOUND = "unbound"
    INELIGIBLE_ONLY = "ineligible_only"


class WorkspaceEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True, slots=True)
class WorkspaceDiscoveryQuery:
    """Intake context used to discover a governed workspace."""

    tenant_id: str
    endpoint_id: str
    location_kind: LocationKind
    external_location_id: str
    parent_location_kind: LocationKind | None = None
    parent_external_location_id: str | None = None
    repository_provider: str | None = None
    external_repository_id: str | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.endpoint_id, "endpoint_id")
        if not self.external_location_id.strip():
            raise MalformedCommandError("external_location_id is required")
        parent_kind = self.parent_location_kind
        parent_id = self.parent_external_location_id
        if (parent_kind is None) != (parent_id is None or not str(parent_id).strip()):
            raise MalformedCommandError(
                "parent_location_kind and parent_external_location_id must be set together"
            )
        repo_provider = self.repository_provider
        repo_id = self.external_repository_id
        if (repo_provider is None or not str(repo_provider).strip()) != (
            repo_id is None or not str(repo_id).strip()
        ):
            raise MalformedCommandError(
                "repository_provider and external_repository_id must be set together"
            )


@dataclass(frozen=True, slots=True)
class WorkspaceCandidate:
    workspace_object_id: str
    score: int
    eligibility: WorkspaceEligibility
    match_reasons: tuple[str, ...]
    eligibility_reasons: tuple[str, ...]
    binding_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_opaque_id(self.workspace_object_id, "workspace_object_id")


@dataclass(frozen=True, slots=True)
class WorkspaceDiscoveryResult:
    outcome: WorkspaceDiscoveryOutcome
    query: WorkspaceDiscoveryQuery
    candidates: tuple[WorkspaceCandidate, ...] = ()
    selected_workspace_object_id: str | None = None
    summary_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.outcome is WorkspaceDiscoveryOutcome.SELECTED
            and self.selected_workspace_object_id is None
        ):
            raise MalformedCommandError("selected outcome requires selected workspace")
        if (
            self.outcome is not WorkspaceDiscoveryOutcome.SELECTED
            and self.selected_workspace_object_id is not None
        ):
            raise MalformedCommandError(
                "selected_workspace_object_id only valid for selected outcome"
            )


@dataclass
class _Accumulator:
    score: int = 0
    match_reasons: list[str] | None = None
    binding_ids: list[str] | None = None

    def __post_init__(self) -> None:
        if self.match_reasons is None:
            self.match_reasons = []
        if self.binding_ids is None:
            self.binding_ids = []

    def add(self, *, points: int, reason: str, binding_id: str) -> None:
        assert self.match_reasons is not None
        assert self.binding_ids is not None
        self.score += points
        if reason not in self.match_reasons:
            self.match_reasons.append(reason)
        if binding_id not in self.binding_ids:
            self.binding_ids.append(binding_id)


def _score_location_kind(kind: LocationKind) -> int:
    return _LOCATION_SPECIFICITY.get(kind, 5)


def evaluate_workspace_discovery(
    query: WorkspaceDiscoveryQuery,
    *,
    exact_location_binding: CollaborationLocationBinding | None,
    parent_location_binding: CollaborationLocationBinding | None,
    repository_binding: RepositoryBinding | None,
    workspace_statuses: Mapping[str, str],
) -> WorkspaceDiscoveryResult:
    """Rank and explain workspace candidates from active bindings.

    Pure evaluation: callers supply already-filtered active bindings.
    """

    for binding in (exact_location_binding, parent_location_binding):
        if binding is not None and binding.status is not WorkspaceBindingStatus.ACTIVE:
            raise MalformedCommandError("discovery requires active location bindings")
    if (
        repository_binding is not None
        and repository_binding.status is not WorkspaceBindingStatus.ACTIVE
    ):
        raise MalformedCommandError("discovery requires an active repository binding")

    accumulated: dict[str, _Accumulator] = {}

    def touch(workspace_object_id: str) -> _Accumulator:
        return accumulated.setdefault(workspace_object_id, _Accumulator())

    if exact_location_binding is not None:
        if exact_location_binding.tenant_id != query.tenant_id:
            raise MalformedCommandError("exact location binding tenant mismatch")
        touch(exact_location_binding.workspace_object_id).add(
            points=100 + _score_location_kind(query.location_kind),
            reason="location.exact",
            binding_id=exact_location_binding.binding_id,
        )

    if parent_location_binding is not None:
        if parent_location_binding.tenant_id != query.tenant_id:
            raise MalformedCommandError("parent location binding tenant mismatch")
        touch(parent_location_binding.workspace_object_id).add(
            points=40 + _score_location_kind(parent_location_binding.location_kind),
            reason="location.parent",
            binding_id=parent_location_binding.binding_id,
        )

    if repository_binding is not None:
        if repository_binding.tenant_id != query.tenant_id:
            raise MalformedCommandError("repository binding tenant mismatch")
        touch(repository_binding.workspace_object_id).add(
            points=50,
            reason="repository.exact",
            binding_id=repository_binding.binding_id,
        )

        location_workspaces = {
            workspace_id
            for workspace_id, bucket in accumulated.items()
            if "location.exact" in (bucket.match_reasons or [])
            or "location.parent" in (bucket.match_reasons or [])
        }
        repo_workspace = repository_binding.workspace_object_id
        if location_workspaces and repo_workspace not in location_workspaces:
            for workspace_id, bucket in accumulated.items():
                if workspace_id == repo_workspace or workspace_id in location_workspaces:
                    assert bucket.match_reasons is not None
                    if "conflict.location_repository" not in bucket.match_reasons:
                        bucket.match_reasons.append("conflict.location_repository")
        elif repo_workspace in location_workspaces:
            bucket = accumulated[repo_workspace]
            assert bucket.match_reasons is not None
            if "agreement.location_repository" not in bucket.match_reasons:
                bucket.match_reasons.append("agreement.location_repository")
                bucket.score += 25

    candidates: list[WorkspaceCandidate] = []
    for workspace_object_id, bucket in accumulated.items():
        status = workspace_statuses.get(workspace_object_id, "active")
        if status.lower() in _INACTIVE_WORKSPACE_STATUSES:
            eligibility = WorkspaceEligibility.INELIGIBLE
            eligibility_reasons = (f"ineligible.workspace_status:{status}",)
        else:
            eligibility = WorkspaceEligibility.ELIGIBLE
            eligibility_reasons = ("eligible.active_workspace",)
        candidates.append(
            WorkspaceCandidate(
                workspace_object_id=workspace_object_id,
                score=bucket.score,
                eligibility=eligibility,
                match_reasons=tuple(bucket.match_reasons or ()),
                eligibility_reasons=eligibility_reasons,
                binding_ids=tuple(bucket.binding_ids or ()),
            )
        )

    candidates.sort(
        key=lambda c: (
            0 if c.eligibility is WorkspaceEligibility.ELIGIBLE else 1,
            -c.score,
            c.workspace_object_id,
        )
    )
    ranked = tuple(candidates)
    eligible = [c for c in ranked if c.eligibility is WorkspaceEligibility.ELIGIBLE]

    if not ranked:
        return WorkspaceDiscoveryResult(
            outcome=WorkspaceDiscoveryOutcome.UNBOUND,
            query=query,
            candidates=(),
            summary_reasons=("unbound.no_active_bindings",),
        )
    if not eligible:
        return WorkspaceDiscoveryResult(
            outcome=WorkspaceDiscoveryOutcome.INELIGIBLE_ONLY,
            query=query,
            candidates=ranked,
            summary_reasons=("ineligible.no_eligible_candidates",),
        )
    if len(eligible) == 1:
        winner = eligible[0]
        return WorkspaceDiscoveryResult(
            outcome=WorkspaceDiscoveryOutcome.SELECTED,
            query=query,
            candidates=ranked,
            selected_workspace_object_id=winner.workspace_object_id,
            summary_reasons=("selected.unique_eligible_candidate",) + winner.match_reasons,
        )
    return WorkspaceDiscoveryResult(
        outcome=WorkspaceDiscoveryOutcome.AMBIGUOUS,
        query=query,
        candidates=ranked,
        summary_reasons=("ambiguous.multiple_eligible_candidates",),
    )
