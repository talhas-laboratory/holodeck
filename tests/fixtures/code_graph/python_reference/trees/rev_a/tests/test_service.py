from sample_app.service import Greeter


def test_greeter_message() -> None:
    assert Greeter().greet("world") == "hello world"
