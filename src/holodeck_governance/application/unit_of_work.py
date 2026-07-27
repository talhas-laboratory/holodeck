"""Unit-of-work protocol (no storage imports)."""

from __future__ import annotations

from typing import Any, Callable, Protocol


SUCCESS_WRITE_SET: tuple[str, ...] = (
    "receipt",
    "evaluation",
    "transition",
    "event",
    "outbox",
    "head",
)


class UnitOfWork(Protocol):
    def add(self, name: str, writer: Callable[[Any], None]) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
