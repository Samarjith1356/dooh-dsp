import pytest

from app.state_machine import InvalidTransition, compiles, transition


def test_happy_path():
    assert transition("draft", "pending_approval") == "pending_approval"
    assert transition("pending_approval", "active") == "active"
    assert compiles("active")
    assert not compiles("draft")


def test_illegal():
    with pytest.raises(InvalidTransition):
        transition("draft", "active")
