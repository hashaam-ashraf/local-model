import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests use a fake model and an in-memory index; any real connection is a bug."""

    def blocked(*args, **kwargs):
        raise RuntimeError("Network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
