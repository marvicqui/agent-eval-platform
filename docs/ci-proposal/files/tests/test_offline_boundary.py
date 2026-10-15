"""Verify that the proposed test guard rejects accidental TCP connections."""
import socket

import pytest


def test_tcp_connection_is_denied() -> None:
    with (
        socket.socket() as connection,
        pytest.raises(AssertionError, match="Network access is disabled"),
    ):
        connection.connect(("127.0.0.1", 9))


def test_connection_helper_is_denied() -> None:
    with pytest.raises(AssertionError, match="Network access is disabled"):
        socket.create_connection(("127.0.0.1", 9))
