"""Shared fixtures for the "misc" API tests (integrations, triggers, plugins,
audit, logs, metrics, import, ws).

Each fixture arranges real rows in the per-test SQLite database; nothing here
mocks the database or the ORM.
"""

import pytest_asyncio
from sqlalchemy import select

from app.main import app
from app.models.integration import Integration
from app.models.peer import Peer
from app.models.server import Server
from app.models.settings import GlobalSettings

PLUGIN_SOURCE = '''\
"""Demo plugin used by the API tests."""
from app.plugins.base import plugin, on_event


@plugin(
    name="Demo Plugin",
    version="1.0.0",
    description="A plugin used in tests",
    author="tester",
)
class DemoPlugin:
    """Minimal plugin that records server creation events."""

    def __init__(self, context):
        self.context = context

    @staticmethod
    def get_config_schema():
        return {"api_key": {"type": "string", "required": True}}

    @on_event("server.created")
    async def handle_server_created(self, event_data):
        return None
'''


@pytest_asyncio.fixture
async def plugins_dir(tmp_path, seeded_db, db_session):
    """Create a real plugins directory and point the setting at it."""
    directory = tmp_path / "plugins"
    plugin_dir = directory / "demo_plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(PLUGIN_SOURCE)
    (plugin_dir / "requirements.txt").write_text("httpx>=0.24\n# comment\n")

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.plugins_directory = str(directory)
    await db_session.commit()

    yield directory

    # The plugin manager is a process-wide singleton; never leak loaded state
    # into other tests.
    manager = app.container.plugin_manager()
    manager.loaded_plugins.clear()
    manager._event_handlers_registered = False


@pytest_asyncio.fixture
async def server(db_session):
    """A persisted WireGuard server."""
    row = Server(
        name="srv-main",
        interface="wg0",
        public_key="server-public-key",
        private_key="server-private-key",
        listen_port=51820,
        ipv4_address="10.0.0.1/24",
        endpoint="vpn.example.com",
        rx_bytes=1500,
        tx_bytes=500,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest_asyncio.fixture
async def peer(db_session, server):
    """A persisted peer attached to :func:`server`."""
    row = Peer(
        server_id=server.id,
        name="peer-main",
        public_key="peer-public-key",
        private_key="peer-private-key",
        ipv4_address="10.0.0.2",
        rx_bytes=700,
        tx_bytes=300,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest_asyncio.fixture
async def integration(db_session):
    """A persisted webhook integration."""
    row = Integration(
        name="Ops webhook",
        description="posts events",
        type="webhook",
        config={"url": "https://hooks.example.com/linguard"},
        events_subscribed=["server.created"],
        enabled=True,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row
