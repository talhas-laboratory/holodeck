from sample_app.service import Greeter


def test_greeter_message() -> None:
    assert Greeter().greet("world") == "hi world"


def test_greeter_shout() -> None:
    assert Greeter().shout("world") == "HI WORLD"
