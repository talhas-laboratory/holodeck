"""Simple file-backed store demonstrating reads and writes."""

from __future__ import annotations

from pathlib import Path


class ItemStore:
    def __init__(self, path: str = "data/items.json") -> None:
        self._path = Path(path)

    def read_message(self) -> str:
        return self._path.read_text(encoding="utf-8")

    def write_message(self, message: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(message, encoding="utf-8")
