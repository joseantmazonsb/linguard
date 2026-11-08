"""Fixtures shared by the servers API tests (real SQLite DB, stubbed host I/O)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

from app.main import app
from app.models.peer import Peer
from app.models.server import Server

SERVER_DEFAULTS = {
    "public_key": "s" * 44,
    "private_key": "t" * 44,
    "listen_port": 51820,
    "ipv4_address": "10.8.0.1/24",
    "ipv6_address": "fd00:8::1/64",
}

PEER_DEFAULTS = {
    "public_key": "p" * 44,
    "private_key": "q" * 44,
    "ipv4_address": "10.8.0.2/24",
}


@pytest_asyncio.fixture
async def make_server(db_session):
    """Factory creating committed Server rows (no transaction stays open)."""
    created = []

    async def _make(**overrides):
        values = {"name": f"srv{len(created) + 1}", **SERVER_DEFAULTS}
        values.update(overrides)
        server = Server(**values)
        db_session.add(server)
        await db_session.commit()
        created.append(server)
        return server

    return _make


@pytest_asyncio.fixture
async def make_peer(db_session):
    """Factory creating committed Peer rows attached to a server."""
    created = []

    async def _make(server_id, **overrides):
        values = {"name": f"peer{len(created) + 1}", **PEER_DEFAULTS}
        values.update(overrides)
        peer = Peer(server_id=server_id, **values)
        db_session.add(peer)
        await db_session.commit()
        created.append(peer)
        return peer

    return _make


@pytest.fixture
def wg():
    """Stub host-facing WireGuard operations on the container's service."""
    service = app.container.wireguard_service()
    stub = SimpleNamespace(interface=None)

    with patch.object(service, "find_interface_by_public_key", side_effect=lambda key: stub.interface), patch.object(
        service, "start_interface", new=AsyncMock(return_value=True)
    ), patch.object(service, "reload_interface", new=AsyncMock(return_value=True)), patch.object(
        service, "stop_interface", Mock(return_value=True)
    ):
        stub.find_interface_by_public_key = service.find_interface_by_public_key
        stub.start_interface = service.start_interface
        stub.reload_interface = service.reload_interface
        stub.stop_interface = service.stop_interface
        yield stub


@pytest.fixture
def wg_installed():
    """Pretend the ``wg`` binary is present on the host."""
    with patch("app.api.servers.detect_wireguard_binaries", return_value={"wg": "/usr/bin/wg"}):
        yield


@pytest.fixture
def fake_keypair():
    """Avoid shelling out to ``wg genkey`` during autofill calls."""
    service = app.container.wireguard_service()
    with patch.object(service, "generate_keypair", return_value=("priv-key", "pub-key")):
        yield
