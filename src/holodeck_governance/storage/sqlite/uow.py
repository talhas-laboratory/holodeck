"""SQLite-backed unit of work."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Callable


FaultPoint = str | None


@dataclass
class SqliteUnitOfWork:
    """Single transactional boundary for governed persistence."""

    conn: sqlite3.Connection
    fault_before: FaultPoint = None
    _pending: list[tuple[str, Callable[[sqlite3.Connection], None]]] = field(
        default_factory=list
    )
    _committed: bool = False

    def add(self, name: str, writer: Callable[[sqlite3.Connection], None]) -> None:
        if self._committed:
            raise RuntimeError("unit of work already committed")
        self._pending.append((name, writer))

    def commit(self) -> None:
        if self._committed:
            return
        previous = self.conn.isolation_level
        self.conn.isolation_level = None
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            for name, writer in self._pending:
                if self.fault_before == name:
                    raise RuntimeError(f"injected fault before {name}")
                writer(self.conn)
                if self.fault_before == f"after:{name}":
                    raise RuntimeError(f"injected fault after {name}")
            self.conn.execute("COMMIT")
            self._committed = True
            self._pending.clear()
        except Exception:
            self.conn.execute("ROLLBACK")
            self._pending.clear()
            raise
        finally:
            self.conn.isolation_level = previous

    def rollback(self) -> None:
        self._pending.clear()
        try:
            self.conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
