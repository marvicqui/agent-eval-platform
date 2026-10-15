"""Keep unit tests deterministic by rejecting outbound Python socket connections."""
import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mocked evaluator must not silently fall back to a real network client."""
    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access is disabled in unit tests")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
