"""Composition root: wire application services to storage gateways.

Adapters may import this module. Application modules must not import it.
"""

from __future__ import annotations

from holodeck_governance.application.commands import GovernanceApplicationService
from holodeck_governance.storage.sqlite.gateway import SqliteGovernanceGateway


def open_governance_app(
    database: str,
    *,
    bootstrap_actor_id: str | None = None,
) -> GovernanceApplicationService:
    gateway = SqliteGovernanceGateway(
        database, bootstrap_actor_id=bootstrap_actor_id
    )
    return GovernanceApplicationService(commands=gateway, reconstruction=gateway)
