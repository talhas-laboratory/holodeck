"""Service layer with a deliberate unresolved dynamic call."""

from sample_app.base import Animal
from sample_app.store import ItemStore


class Greeter(Animal):
    """Greets callers and persists a message."""

    kind = "greeter"

    def __init__(self, store: ItemStore | None = None) -> None:
        self._store = store or ItemStore()

    def greet(self, name: str) -> str:
        message = f"hi {name}"
        self._store.write_message(message)
        return message

    def shout(self, name: str) -> str:
        return self.greet(name).upper()

    def invoke(self, handler_name: str) -> None:
        # Intentionally unresolved: target depends on a runtime string.
        handler = globals()[handler_name]
        handler()
