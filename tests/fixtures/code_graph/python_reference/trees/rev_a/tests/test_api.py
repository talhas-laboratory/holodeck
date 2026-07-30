from sample_app.api import handle_greet


def test_handle_greet() -> None:
    assert handle_greet("ada") == "hello ada"
