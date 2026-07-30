"""Reversible workspace-genesis proposals and human decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from holodeck_governance.domain.collaboration.types import LocationKind
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc


class GenesisProposalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class GenesisDecisionOutcome(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    WITHDRAW = "withdraw"


# Role-profile permissions required at the genesis application boundary.
GENESIS_PROPOSE_PERMISSION = "workspace.genesis.propose"
GENESIS_DECIDE_PERMISSION = "workspace.genesis.decide"

# Durable domain-event type strings (M2 genesis ledger).
GENESIS_EVENT_PROPOSED = "workspace.genesis.proposed"
GENESIS_EVENT_DECIDED = "workspace.genesis.decided"
GENESIS_EVENT_SCHEMA_VERSION = "m2.workspace.genesis.event.v1"


@dataclass(frozen=True, slots=True)
class WorkspaceGenesisProposal:
    """Proposed creation of a Holodeck workspace for an unbound location.

    Remains reversible until an explicit human decision is recorded. The
    collaboration location is never itself the workspace.
    """

    proposal_id: str
    tenant_id: str
    endpoint_id: str
    location_kind: LocationKind
    external_location_id: str
    location_reference_id: str
    proposed_workspace_object_id: str
    display_name: str
    purpose_text: str
    status: GenesisProposalStatus
    created_at: datetime
    created_by_actor_id: str
    discovery_reason_codes: tuple[str, ...] = ()
    repository_provider: str | None = None
    external_repository_id: str | None = None
    repository_reference_id: str | None = None
    decided_at: datetime | None = None
    decided_by_actor_id: str | None = None
    decision_outcome: GenesisDecisionOutcome | None = None
    decision_rationale: str = ""
    schema_version: str = "m2.workspace_genesis_proposal.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("proposal_id", self.proposal_id),
            ("tenant_id", self.tenant_id),
            ("endpoint_id", self.endpoint_id),
            ("location_reference_id", self.location_reference_id),
            ("proposed_workspace_object_id", self.proposed_workspace_object_id),
            ("created_by_actor_id", self.created_by_actor_id),
        ):
            require_opaque_id(value, name)
        require_utc(self.created_at, "created_at")
        if not self.external_location_id.strip():
            raise MalformedCommandError("external_location_id is required")
        if not self.display_name.strip():
            raise MalformedCommandError("display_name is required")
        if not self.purpose_text.strip():
            raise MalformedCommandError("purpose_text is required")
        repo_provider = self.repository_provider
        repo_id = self.external_repository_id
        if (repo_provider is None or not str(repo_provider).strip()) != (
            repo_id is None or not str(repo_id).strip()
        ):
            raise MalformedCommandError(
                "repository_provider and external_repository_id must be set together"
            )
        if self.repository_reference_id is not None:
            require_opaque_id(self.repository_reference_id, "repository_reference_id")
            if repo_provider is None:
                raise MalformedCommandError(
                    "repository_reference_id requires repository fields"
                )
        if self.status is GenesisProposalStatus.PROPOSED:
            if self.decided_at is not None or self.decided_by_actor_id is not None:
                raise MalformedCommandError(
                    "proposed genesis proposals cannot carry a decision"
                )
            if self.decision_outcome is not None:
                raise MalformedCommandError(
                    "proposed genesis proposals cannot carry a decision_outcome"
                )
        else:
            if self.decided_at is None or self.decided_by_actor_id is None:
                raise MalformedCommandError(
                    "decided genesis proposals require decided_at and decided_by_actor_id"
                )
            require_utc(self.decided_at, "decided_at")
            require_opaque_id(self.decided_by_actor_id, "decided_by_actor_id")
            if self.decision_outcome is None:
                raise MalformedCommandError(
                    "decided genesis proposals require decision_outcome"
                )


@dataclass(frozen=True, slots=True)
class WorkspaceGenesisDecision:
    """Human decision closing a reversible genesis proposal."""

    proposal_id: str
    tenant_id: str
    outcome: GenesisDecisionOutcome
    decided_at: datetime
    decided_by_actor_id: str
    rationale: str = ""

    def __post_init__(self) -> None:
        require_opaque_id(self.proposal_id, "proposal_id")
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.decided_by_actor_id, "decided_by_actor_id")
        require_utc(self.decided_at, "decided_at")


def genesis_proposal_open_dedupe_key(
    proposal: WorkspaceGenesisProposal,
) -> tuple[str, str, str, str]:
    """Natural key for at-most-one open proposal per collaboration location."""

    return (
        proposal.tenant_id,
        proposal.endpoint_id,
        proposal.location_kind.value,
        proposal.external_location_id,
    )
