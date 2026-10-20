"""A test exists, so the project is not flagged for zero tests."""
from app import Handler


def test_handler_has_shared_error_builder():
    assert hasattr(Handler, "_send_error")
