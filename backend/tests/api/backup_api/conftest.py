"""Fixtures for the backup API tests.

Every test runs against the real per-test SQLite database from
``tests/conftest.py``. The only thing redirected is the filesystem: the
``backup_dir`` setting is pointed at ``tmp_path`` so backups never touch the
repository's ``./backups`` directory.
"""

import pytest_asyncio
from sqlalchemy import select

from app.models.peer import Peer
from app.models.server import Server
from app.models.settings import GlobalSettings


@pytest_asyncio.fixture
async def backup_dir(tmp_path, seeded_db, db_session):
    """Point the global ``backup_dir`` setting at a temporary directory."""
    directory = tmp_path / "backups"
    result = await db_session.execute(select(GlobalSettings))
    settings = result.scalar_one()
    settings.backup_dir = str(directory)
    await db_session.commit()
    return directory


@pytest_asyncio.fixture
async def seeded_server_and_peer(db_session):
    """One server with one peer, so backups contain real data."""
    server = Server(
        name="srv-main",
        interface="wg0",
        public_key="server-public-key",
        private_key="server-private-key",
        listen_port=51820,
        ipv4_address="10.0.0.1/24",
        endpoint="vpn.example.com",
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)

    peer = Peer(
        server_id=server.id,
        name="peer-main",
        public_key="peer-public-key",
        private_key="peer-private-key",
        ipv4_address="10.0.0.2",
    )
    db_session.add(peer)
    await db_session.commit()
    await db_session.refresh(peer)

    return {"server_id": server.id, "peer_id": peer.id}
