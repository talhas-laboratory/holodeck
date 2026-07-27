"""Application command and reconstruction ports (storage-independent)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from holodeck_governance.domain.commands.envelope import CommandEnvelope
from holodeck_governance.domain.commands.receipt import CommandReceipt


class GovernanceCommandPort(Protocol):
    def handle(
        self, command: CommandEnvelope, *, now: datetime | None = None
    ) -> CommandReceipt: ...


class GovernanceReconstructionPort(Protocol):
    def reconstruct(self, *, tenant_id: str, command_id: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class GovernanceApplicationService:
    """Adapter-facing orchestration seam.

    Adapters depend on this service. Storage gateways implement the ports.
    M1 lifecycle mutations enter through ``handle``; reconstruction through
    ``reconstruct``. Bootstrap/admin record writes may use storage repos until
    typed create/command envelopes exist (see DECISIONS.md).
    """

    commands: GovernanceCommandPort
    reconstruction: GovernanceReconstructionPort

    def handle(
        self, command: CommandEnvelope, *, now: datetime | None = None
    ) -> CommandReceipt:
        return self.commands.handle(command, now=now)

    def reconstruct(self, *, tenant_id: str, command_id: str) -> Any:
        return self.reconstruction.reconstruct(
            tenant_id=tenant_id, command_id=command_id
        )
