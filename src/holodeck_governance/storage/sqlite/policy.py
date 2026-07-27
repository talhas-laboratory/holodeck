"""Policy binding persistence and activation (M1-018)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from holodeck_governance.domain.policy.binding import PolicyBinding
from holodeck_governance.storage.sqlite.migrations import migrate_governance


class SqlitePolicyRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        migrate_governance(conn)

    def save(self, binding: PolicyBinding) -> None:
        self._conn.execute(
            """
            INSERT INTO gov_policy_bindings(
                binding_id, tenant_id, scope, evaluator_id, parameters_json,
                created_at, created_by_actor_id, precedence, effective_from,
                effective_until, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding.binding_id,
                binding.tenant_id,
                binding.scope,
                binding.evaluator_id,
                json.dumps(dict(binding.parameters), sort_keys=True),
                binding.created_at.isoformat(),
                binding.created_by_actor_id,
                binding.precedence,
                binding.effective_from.isoformat(),
                binding.effective_until.isoformat() if binding.effective_until else None,
                binding.schema_version,
            ),
        )

    def list_for_tenant(self, tenant_id: str) -> list[PolicyBinding]:
        rows = self._conn.execute(
            "SELECT * FROM gov_policy_bindings WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchall()
        return [_row_to_binding(row) for row in rows]

    def active_parameters(
        self,
        *,
        tenant_id: str,
        evaluator_id: str,
        at: datetime,
    ) -> dict[str, str]:
        params, _ids = self.active_policy(
            tenant_id=tenant_id, evaluator_id=evaluator_id, at=at
        )
        return params

    def active_policy(
        self,
        *,
        tenant_id: str,
        evaluator_id: str,
        at: datetime,
    ) -> tuple[dict[str, str], tuple[str, ...]]:
        from holodeck_governance.domain.policy.binding import resolve_active_policy

        return resolve_active_policy(
            self.list_for_tenant(tenant_id),
            evaluator_id=evaluator_id,
            at=at,
        )


def _row_to_binding(row: sqlite3.Row) -> PolicyBinding:
    until = row["effective_until"]
    return PolicyBinding(
        binding_id=str(row["binding_id"]),
        tenant_id=str(row["tenant_id"]),
        scope=str(row["scope"]),
        evaluator_id=str(row["evaluator_id"]),
        parameters=dict(json.loads(str(row["parameters_json"]))),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        created_by_actor_id=str(row["created_by_actor_id"]),
        precedence=int(row["precedence"]),
        effective_from=datetime.fromisoformat(str(row["effective_from"])),
        effective_until=datetime.fromisoformat(str(until)) if until else None,
        schema_version=str(row["schema_version"]),
    )
