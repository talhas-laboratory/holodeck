"""Composition root: wire application services to storage gateways.

Adapters may import this module. Application modules must not import it.
"""

from __future__ import annotations

import sqlite3

from holodeck_governance.application.collaboration import CollaborationApplicationService
from holodeck_governance.application.commands import GovernanceApplicationService
from holodeck_governance.application.workspace_intelligence import (
    WorkspaceIntelligenceApplicationService,
)
from holodeck_governance.storage.sqlite.collaboration import SqliteCollaborationRepository
from holodeck_governance.storage.sqlite.gateway import SqliteGovernanceGateway
from holodeck_governance.storage.sqlite.intelligence import (
    SqliteWorkspaceIntelligenceRepository,
)
from holodeck_governance.storage.sqlite.migrations import migrate_governance


def open_governance_app(
    database: str,
    *,
    bootstrap_actor_id: str | None = None,
) -> GovernanceApplicationService:
    gateway = SqliteGovernanceGateway(
        database, bootstrap_actor_id=bootstrap_actor_id
    )
    return GovernanceApplicationService(commands=gateway, reconstruction=gateway)


def open_collaboration_app(database: str) -> CollaborationApplicationService:
    """Open the collaboration binding/receipt seam on the governance database."""

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_governance(conn)
    return CollaborationApplicationService(
        repository=SqliteCollaborationRepository(conn)
    )


def open_workspace_intelligence_app(
    database: str,
) -> WorkspaceIntelligenceApplicationService:
    """Open the workspace-intelligence seam on the governance database."""

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_governance(conn)
    return WorkspaceIntelligenceApplicationService(
        repository=SqliteWorkspaceIntelligenceRepository(conn)
    )
