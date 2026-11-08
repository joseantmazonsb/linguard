"""Tests for ``app.services.backup_service`` -- export, restore and reporting.

The service writes real JSON files to a temporary backup directory and all
database work runs against the real per-test SQLite database.
"""

import base64
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.backup import Backup
from app.models.integration import Integration
from app.models.peer import Peer
from app.models.plugin import Plugin
from app.models.server import Server
from app.models.settings import GlobalSettings
from app.models.traffic_trigger import TrafficScope, TrafficTrigger
from app.services.backup_service import BackupService


class StubSettingsService:
    def __init__(self, directory):
        self.directory = str(directory)

    async def get_backup_dir(self, db):
        return self.directory


@pytest.fixture
def backup_dir(tmp_path):
    path = tmp_path / "backups"
    path.mkdir()
    return path


@pytest.fixture
def service(backup_dir):
    return BackupService(settings_service=StubSettingsService(backup_dir))


@pytest.fixture
async def populated(seeded_db, db_session):
    """A database with one server, two peers, integration, trigger and plugin."""
    server = Server(
        name="Tokyo", interface="wg0", description="primary",
        public_key="x" * 44, private_key="y" * 44, endpoint="vpn.example.com",
        listen_port=51820, ipv4_address="10.8.0.1/24", ipv6_address="fd00::1/64",
        dns_primary="1.1.1.1", dns_secondary="9.9.9.9", is_bounce_server=False, enabled=True,
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)

    peers = [
        Peer(server_id=server.id, name="alice", email="alice@example.com",
             public_key="a" * 44, private_key="b" * 44, preshared_key="c" * 44,
             ipv4_address="10.8.0.2", ipv6_address="fd00::2",
             ipv4_allowed_ips="0.0.0.0/0", ipv6_allowed_ips="::/0",
             dns_primary="8.8.8.8", persistent_keepalive=25, enabled=True),
        Peer(server_id=server.id, name="bob", public_key="d" * 44, private_key="e" * 44,
             ipv4_address="10.8.0.3", enabled=False),
    ]
    plugin = Plugin(name="Slack", version="1.0", module_name="slack", file_path="/plugins/slack/plugin.py",
                    config={"url": "https://hooks"}, enabled=True, subscribed_events=["peer.created"],
                    requirements=["httpx"])
    db_session.add_all(peers + [plugin])
    await db_session.commit()
    await db_session.refresh(plugin)
    for peer in peers:
        await db_session.refresh(peer)

    integration = Integration(
        name="webhook", type="webhook", config={"url": "https://example.com/hook"},
        events_subscribed=["peer.created"], enabled=True, plugin_id=plugin.id,
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    trigger = TrafficTrigger(
        name="daily", scope=TrafficScope.PEER, peer_id=peers[0].id, server_id=server.id,
        direction="combined", threshold_bytes=1_000_000, window="last_24_hours",
        cooldown_seconds=3600, enabled=True, trigger_integrations=[integration.id],
    )
    db_session.add(trigger)
    await db_session.commit()

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.dns_primary = "10.8.0.1"
    settings.dns_secondary = "10.9.0.1"
    await db_session.commit()

    return {
        "server": server, "peers": peers, "plugin": plugin,
        "integration": integration, "trigger": trigger,
    }


async def backup_file(backup_dir, backup):
    return json.loads((backup_dir / backup.filename).read_text())


# ===========================================================================
# create_backup
# ===========================================================================

class TestCreateBackup:
    async def test_should_export_every_table_to_json(self, service, db_session, backup_dir, populated):
        with patch("app.services.backup_service.event_bus.publish", new=AsyncMock()) as publish:
            backup = await service.create_backup(db_session, user_id=1, description="nightly")

        data = await backup_file(backup_dir, backup)

        assert data["version"] == "1.0"
        assert data["global_settings"] == {"dns_primary": "10.8.0.1", "dns_secondary": "10.9.0.1"}
        assert len(data["servers"]) == 1
        server = data["servers"][0]
        assert server["name"] == "Tokyo"
        assert server["private_key"] == "y" * 44
        assert (server["ipv4_address"], server["ipv6_address"]) == ("10.8.0.1/24", "fd00::1/64")
        assert [p["name"] for p in data["peers"]] == ["alice", "bob"]
        assert data["peers"][0]["preshared_key"] == "c" * 44
        assert data["peers"][1]["enabled"] is False
        assert data["integrations"][0]["config"] == {"url": "https://example.com/hook"}
        assert data["traffic_triggers"][0]["threshold_bytes"] == 1_000_000
        assert data["plugins"][0]["requirements"] == ["httpx"]

        # metadata recorded on the Backup row
        assert backup.servers_count == 1
        assert backup.peers_count == 2
        assert backup.integrations_count == 1
        assert backup.traffic_triggers_count == 1
        assert backup.plugins_count == 1
        assert backup.is_encrypted is False
        assert backup.description == "nightly"
        assert backup.created_by_user_id == 1
        assert backup.size_bytes == (backup_dir / backup.filename).stat().st_size

        publish.assert_awaited_once()
        event_payload = publish.await_args.args[3]
        assert event_payload["filename"] == backup.filename
        assert event_payload["peers_count"] == 2
        assert event_payload["encrypted"] is False

    async def test_should_name_file_with_timestamp(self, service, db_session, backup_dir, populated):
        backup = await service.create_backup(db_session, user_id=1)

        assert backup.filename.startswith("wireguard_backup_")
        assert backup.filename.endswith(".json")
        # wireguard_backup_YYYYmmdd_HHMMSS_mmm.json
        stamp = backup.filename[len("wireguard_backup_"):-len(".json")].split("_")
        assert len(stamp) == 3
        datetime.strptime(f"{stamp[0]}_{stamp[1]}", "%Y%m%d_%H%M%S")
        assert len(stamp[2]) == 3

    async def test_should_add_counter_when_filename_already_on_disk(
            self, service, db_session, backup_dir, populated, monkeypatch):
        class FrozenDatetime(datetime):
            @classmethod
            def utcnow(cls):
                return datetime(2026, 1, 2, 3, 4, 5, 678000)

        monkeypatch.setattr("app.services.backup_service.datetime", FrozenDatetime)
        (backup_dir / "wireguard_backup_20260102_030405_678.json").write_text("{}")

        backup = await service.create_backup(db_session, user_id=1)

        assert backup.filename == "wireguard_backup_20260102_030405_678_1.json"
        assert (backup_dir / backup.filename).exists()

    async def test_should_add_counter_when_filename_already_in_database(
            self, service, db_session, backup_dir, populated, monkeypatch):
        class FrozenDatetime(datetime):
            @classmethod
            def utcnow(cls):
                return datetime(2026, 1, 2, 3, 4, 5, 678000)

        monkeypatch.setattr("app.services.backup_service.datetime", FrozenDatetime)
        db_session.add(Backup(filename="wireguard_backup_20260102_030405_678.json",
                              size_bytes=2, created_by_user_id=1))
        await db_session.commit()

        backup = await service.create_backup(db_session, user_id=1)

        assert backup.filename == "wireguard_backup_20260102_030405_678_1.json"

    async def test_should_never_encrypt_even_when_encryption_is_requested(
            self, service, db_session, backup_dir, populated):
        backup = await service.create_backup(db_session, user_id=1, encrypt=True, passphrase="pw")

        assert backup.is_encrypted is False
        # The JSON is still plain text (encryption is not implemented yet)
        assert "servers" in (backup_dir / backup.filename).read_text()

    async def test_should_use_default_directory_without_settings_service(
            self, db_session, populated, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        backup = await BackupService().create_backup(db_session, user_id=1)

        assert (tmp_path / "backups" / backup.filename).exists()


# ===========================================================================
# restore_backup
# ===========================================================================

class TestRestoreBackup:
    async def test_should_recreate_missing_entities(self, service, db_session, populated):
        backup = await service.create_backup(db_session, user_id=1)

        # Simulate data loss
        await db_session.execute(Peer.__table__.delete())
        await db_session.execute(TrafficTrigger.__table__.delete())
        await db_session.execute(Integration.__table__.delete())
        await db_session.execute(Server.__table__.delete())
        await db_session.commit()

        with patch("app.services.backup_service.event_bus.publish", new=AsyncMock()) as publish:
            summary = await service.restore_backup(db_session, backup.id, user_id=1)

        assert summary == {
            "success": True,
            "servers_restored": 1,
            "peers_restored": 2,
            "integrations_restored": 1,
            "traffic_triggers_restored": 1,
            "plugins_restored": 1,
            "cleared_existing": False,
        }
        peers = (await db_session.execute(select(Peer).order_by(Peer.name))).scalars().all()
        assert [p.name for p in peers] == ["alice", "bob"]
        assert peers[0].preshared_key == "c" * 44
        assert peers[0].ipv4_address == "10.8.0.2"
        servers = (await db_session.execute(select(Server))).scalars().all()
        assert [s.name for s in servers] == ["Tokyo"]
        # triggers keep pointing at the restored peer
        trigger = (await db_session.execute(select(TrafficTrigger))).scalars().one()
        assert trigger.peer_id == peers[0].id
        publish.assert_awaited_once()

    async def test_should_skip_existing_entities_and_map_ids(self, service, db_session, populated):
        backup = await service.create_backup(db_session, user_id=1)
        await db_session.execute(Peer.__table__.delete())
        await db_session.commit()

        summary = await service.restore_backup(db_session, backup.id, user_id=1)

        # Server + plugin still exist, so only peers and triggers are new
        assert summary["servers_restored"] == 1
        assert summary["peers_restored"] == 2
        assert len((await db_session.execute(select(Server))).scalars().all()) == 1
        peers = (await db_session.execute(select(Peer))).scalars().all()
        assert len(peers) == 2
        assert {p.server_id for p in peers} == {populated["server"].id}

    async def test_should_clear_existing_data_when_requested(self, service, db_session, populated):
        backup = await service.create_backup(db_session, user_id=1)
        extra = Peer(server_id=populated["server"].id, name="temp", public_key="z" * 44,
                     private_key="z" * 44, ipv4_address="10.8.0.9")
        db_session.add(extra)
        await db_session.commit()

        summary = await service.restore_backup(db_session, backup.id, user_id=1, clear_existing=True)

        assert summary["cleared_existing"] is True
        names = [p.name for p in (await db_session.execute(select(Peer))).scalars().all()]
        assert "temp" not in names
        assert sorted(names) == ["alice", "bob"]
        # plugins are discovered from disk, so they survive a clear
        assert (await db_session.execute(select(Plugin))).scalars().one().name == "Slack"

    async def test_should_restore_global_settings_dns(self, service, db_session, populated):
        backup = await service.create_backup(db_session, user_id=1)
        settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
        settings.dns_primary = "0.0.0.0"
        await db_session.commit()

        await service.restore_backup(db_session, backup.id, user_id=1)

        await db_session.refresh(settings)
        assert settings.dns_primary == "10.8.0.1"
        assert settings.dns_secondary == "10.9.0.1"

    async def test_should_update_existing_plugin_config_and_enabled_flag(
            self, service, db_session, populated, backup_dir):
        backup = await service.create_backup(db_session, user_id=1)
        plugin = populated["plugin"]
        plugin.enabled = False
        plugin.config = {}
        await db_session.commit()

        await service.restore_backup(db_session, backup.id, user_id=1)

        await db_session.refresh(plugin)
        assert plugin.enabled is True
        assert plugin.config == {"url": "https://hooks"}

    async def test_should_raise_when_backup_record_missing(self, service, db_session):
        with pytest.raises(ValueError, match="Backup not found"):
            await service.restore_backup(db_session, 4242, user_id=1)

    async def test_should_raise_when_backup_file_missing(self, service, db_session, backup_dir, populated):
        backup = await service.create_backup(db_session, user_id=1)
        (backup_dir / backup.filename).unlink()

        with pytest.raises(ValueError, match="Backup file not found"):
            await service.restore_backup(db_session, backup.id, user_id=1)

    async def test_should_raise_on_corrupt_backup_file(self, service, db_session, backup_dir, populated):
        backup = await service.create_backup(db_session, user_id=1)
        (backup_dir / backup.filename).write_text("{not json")

        with pytest.raises(json.JSONDecodeError):
            await service.restore_backup(db_session, backup.id, user_id=1)

    async def test_should_require_passphrase_for_encrypted_backup(self, service, db_session, backup_dir, populated):
        backup = await service.create_backup(db_session, user_id=1)
        backup.is_encrypted = True
        await db_session.commit()

        with pytest.raises(ValueError, match="Passphrase required for encrypted backup"):
            await service.restore_backup(db_session, backup.id, user_id=1)

    async def test_should_decode_base64_encrypted_payload(self, service, db_session, backup_dir, populated):
        backup = await service.create_backup(db_session, user_id=1)
        path = backup_dir / backup.filename
        encoded = base64.b64encode(path.read_bytes()).decode()
        path.write_text(encoded)
        backup.is_encrypted = True
        await db_session.commit()

        summary = await service.restore_backup(db_session, backup.id, user_id=1, passphrase="secret")

        assert summary["success"] is True
        assert summary["servers_restored"] == 1

    async def test_should_skip_trigger_whose_peer_is_absent(self, service, db_session, backup_dir, populated):
        backup = await service.create_backup(db_session, user_id=1)
        path = backup_dir / backup.filename
        data = json.loads(path.read_text())
        data["peers"] = []  # peers missing from the archive
        path.write_text(json.dumps(data))

        summary = await service.restore_backup(db_session, backup.id, user_id=1)

        assert summary["peers_restored"] == 0
        assert (await db_session.execute(select(TrafficTrigger))).scalars().first() is not None

    async def test_should_skip_integration_of_unknown_plugin(self, service, db_session, backup_dir, populated):
        backup = await service.create_backup(db_session, user_id=1)
        path = backup_dir / backup.filename
        data = json.loads(path.read_text())
        data["integrations"][0]["plugin_id"] = 999  # plugin not present locally
        path.write_text(json.dumps(data))

        summary = await service.restore_backup(db_session, backup.id, user_id=1)

        assert summary["integrations_restored"] == 1  # count reports archive contents
        names = [i.name for i in (await db_session.execute(select(Integration))).scalars().all()]
        assert names == ["webhook"]  # the original one, not a duplicate


# ===========================================================================
# import_backup
# ===========================================================================

class TestImportBackup:
    async def test_should_copy_file_and_record_counts(self, service, db_session, backup_dir, populated, tmp_path):
        source = tmp_path / "upload.json"
        source.write_text(json.dumps({
            "version": "1.0",
            "servers": [{"name": "A"}],
            "peers": [{"name": "P1"}, {"name": "P2"}],
            "integrations": [],
            "traffic_triggers": [{"name": "T"}],
            "plugins": [],
        }))

        backup = await service.import_backup(db_session, str(source), user_id=1)

        assert backup.filename.startswith("wireguard_backup_")
        assert backup.filename.endswith("_imported.json")
        assert (backup_dir / backup.filename).exists()
        assert backup.description == "Imported backup"
        assert (backup.servers_count, backup.peers_count,
                backup.traffic_triggers_count, backup.plugins_count) == (1, 2, 1, 0)
        assert backup.is_encrypted is False

    async def test_should_keep_provided_description(self, service, db_session, populated, tmp_path):
        source = tmp_path / "upload.json"
        source.write_text(json.dumps({"version": "1.0"}))

        backup = await service.import_backup(db_session, str(source), user_id=1, description="from NAS")

        assert backup.description == "from NAS"

    async def test_should_reject_invalid_json(self, service, db_session, populated, tmp_path):
        source = tmp_path / "broken.json"
        source.write_text("{oops")

        with pytest.raises(ValueError, match="Invalid JSON format"):
            await service.import_backup(db_session, str(source), user_id=1)

    async def test_should_reject_archive_without_version(self, service, db_session, populated, tmp_path):
        source = tmp_path / "no-version.json"
        source.write_text(json.dumps({"servers": []}))

        with pytest.raises(ValueError, match="missing version"):
            await service.import_backup(db_session, str(source), user_id=1)


# ===========================================================================
# Reporting helpers
# ===========================================================================

class TestReporting:
    async def test_should_return_empty_status_without_backups(self, service, db_session):
        status = await service.backup_service_status(db_session)

        assert status == {
            "service_running": True,
            "latest_backup_id": None,
            "latest_backup_filename": None,
            "latest_backup_size": 0,
            "latest_backup_created_at": None,
        }

    async def test_should_report_latest_backup_in_status(self, service, db_session, populated):
        first = await service.create_backup(db_session, user_id=1)
        second = await service.create_backup(db_session, user_id=1)

        status = await service.backup_service_status(db_session)

        assert status["latest_backup_id"] == second.id
        assert status["latest_backup_filename"] == second.filename
        assert status["latest_backup_size"] == second.size_bytes
        assert status["latest_backup_created_at"] is not None
        assert first.id != second.id

    async def test_should_list_all_backups_newest_first(self, service, db_session, populated):
        first = await service.create_backup(db_session, user_id=1)
        second = await service.create_backup(db_session, user_id=1)

        backups = await service.get_backups_all(db_session)

        assert [b.id for b in backups] == [second.id, first.id]

    async def test_should_fetch_backup_by_id(self, service, db_session, populated):
        created = await service.create_backup(db_session, user_id=1)

        found = await service.get_backup_by_id(db_session, created.id)

        assert found.id == created.id
        assert await service.get_backup_by_id(db_session, 999) is None

    async def test_should_delete_backup_record(self, service, db_session, populated):
        created = await service.create_backup(db_session, user_id=1)

        assert await service.delete_backup(db_session, created.id) is True
        assert await service.get_backup_by_id(db_session, created.id) is None
        assert await service.delete_backup(db_session, created.id) is False

    async def test_should_report_metrics(self, service, db_session, populated):
        await service.create_backup(db_session, user_id=1)
        second = await service.create_backup(db_session, user_id=1)

        metrics = await service.backup_service_metrics(db_session)

        assert metrics["total_backups"] == 2
        assert metrics["total_size_bytes"] == second.size_bytes * 2
        assert metrics["total_size_mb"] == round(second.size_bytes * 2 / (1024 * 1024), 2)

    async def test_should_return_zero_metrics_without_backups(self, service, db_session):
        assert await service.backup_service_metrics(db_session) == {
            "total_backups": 0,
            "total_size_bytes": 0,
            "total_size_mb": 0.0,
        }

    async def test_should_report_health_based_on_todays_backups(self, service, db_session, populated):
        assert (await service.backup_service_health(db_session))["healthy"] is False

        await service.create_backup(db_session, user_id=1)

        health = await service.backup_service_health(db_session)
        assert health["healthy"] is True
        assert health["recent_backups_count"] == 1

    async def test_should_return_static_settings_and_config(self, service, db_session):
        assert await service.backup_service_logs(db_session) == []
        assert await service.backup_service_config(db_session) == {
            "backup_directory": "backups",
            "retention_days": 30,
            "auto_cleanup_enabled": True,
        }
        assert await service.backup_service_settings(db_session) == {
            "backup_periodic_enabled": False,
            "backup_frequency": "daily",
            "backup_hour": 2,
            "backup_minute": 0,
        }

    async def test_should_filter_backups_with_servers_and_by_type_or_status(
            self, service, db_session, populated):
        with_servers = await service.create_backup(db_session, user_id=1)
        empty = Backup(filename="empty.json", size_bytes=2, servers_count=0, created_by_user_id=1)
        db_session.add(empty)
        await db_session.commit()

        by_server = await service.get_backups_by_server(db_session, 1)
        by_type = await service.get_backups_by_type(db_session, "full")
        by_status = await service.get_backups_by_status(db_session, "completed")

        assert [b.id for b in by_server] == [with_servers.id]
        assert {b.id for b in by_type} == {with_servers.id, empty.id}
        assert {b.id for b in by_status} == {with_servers.id, empty.id}
