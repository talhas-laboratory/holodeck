"""HTTP-shaped API entry points."""

from sample_app.service import Greeter


def create_app() -> dict[str, object]:
    greeter = Greeter()
    return {"greeter": greeter}


def handle_greet(name: str) -> str:
    app = create_app()
    greeter = app["greeter"]
    assert isinstance(greeter, Greeter)
    return greeter.greet(name)
