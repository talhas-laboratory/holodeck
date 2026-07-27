"""Storage protocols (repository interfaces). Implemented under storage.sqlite."""

from __future__ import annotations

from typing import Any, Protocol

from holodeck_governance.domain.commands.receipt import CommandReceipt
from holodeck_governance.domain.tenant import Tenant


class TenantRepository(Protocol):
    def get(self, tenant_id: str) -> Tenant | None: ...

    def get_default_local(self) -> Tenant | None: ...

    def save(self, tenant: Tenant) -> None: ...

    def count(self) -> int: ...


class CommandReceiptRepository(Protocol):
    def get_by_idempotency(self, tenant_id: str, idempotency_key: str) -> CommandReceipt | None: ...

    def save(self, receipt: CommandReceipt, *, idempotency_key: str, semantic_hash: str) -> None: ...


class DomainEventRepository(Protocol):
    def append(self, *, tenant_id: str, event_type: str, payload: dict[str, Any], correlation_id: str, causation_id: str, created_at: str, event_id: str | None = None) -> str: ...


class OutboxRepository(Protocol):
    def enqueue(self, *, tenant_id: str, domain_event_id: str, delivery_purpose: str, dedup_key: str, created_at: str) -> str: ...


class TransitionRecordRepository(Protocol):
    def append(self, *, tenant_id: str, subject_object_id: str, from_state: str, to_state: str, definition_version: str, created_at: str) -> str: ...


class EvaluationRepository(Protocol):
    def save_snapshot_and_result(self, snapshot: Any, result: Any) -> None: ...
