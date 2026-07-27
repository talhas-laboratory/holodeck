"""SQLite gateway implementing application command/reconstruction ports."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from holodeck_governance.domain.commands.envelope import CommandEnvelope
from holodeck_governance.domain.commands.receipt import CommandReceipt
from holodeck_governance.storage.sqlite.command_service import CommandService
from holodeck_governance.storage.sqlite.reconstruction import reconstruct_from_command
from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant


class SqliteGovernanceGateway:
    """Composition root for SQLite-backed governance command handling."""

    def __init__(
        self,
        database: str | sqlite3.Connection,
        *,
        bootstrap_actor_id: str | None = None,
    ) -> None:
        self._database = database
        self._bootstrap_actor_id = bootstrap_actor_id
        self._owns_connection = isinstance(database, str)

    def handle(
        self, command: CommandEnvelope, *, now: datetime | None = None
    ) -> CommandReceipt:
        conn = self._connect()
        try:
            ensure_default_local_tenant(
                conn,
                tenant_id=command.tenant_id,
                created_by_actor_id=self._bootstrap_actor_id or command.actor_id,
            )
            receipt = CommandService(conn).handle(command, now=now)
            if self._owns_connection:
                conn.commit()
            return receipt
        finally:
            if self._owns_connection:
                conn.close()

    def reconstruct(self, *, tenant_id: str, command_id: str) -> Any:
        conn = self._connect()
        try:
            return reconstruct_from_command(
                conn, tenant_id=tenant_id, command_id=command_id
            )
        finally:
            if self._owns_connection:
                conn.close()

    def _connect(self) -> sqlite3.Connection:
        if isinstance(self._database, sqlite3.Connection):
            return self._database
        conn = sqlite3.connect(self._database)
        conn.row_factory = sqlite3.Row
        return conn
