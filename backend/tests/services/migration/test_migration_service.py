"""Tests for ``app.services.migration``.

``migrate_peer`` is the meaningful part: it moves a peer between servers while
preserving key material, re-assigning addresses and inheriting the target
server's DNS. The legacy module-level helpers wrap subprocess calls and are
tested by patching ``subprocess.run`` inside the module under test.
"""

import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from app.models.peer import Peer
from app.models.server import Server
from app.services import migration as migration_module
from app.services.dns_hierarchy import DNSHierarchyService
from app.services.ip_management import IPManagementService
from app.services.migration import MigrationService

PRIVATE_KEY = "A" * 43 + "="
PUBLIC_KEY = "B" * 43 + "="


@pytest.fixture
def service():
    return MigrationService(
        ip_management_service=IPManagementService(),
        dns_hierarchy_service=DNSHierarchyService(),
        audit_service=AsyncMock(),
    )


async def make_server(db, name, ipv4="10.8.0.1/24", ipv6="fd00:8::1/64", dns_primary=None,
                      dns_secondary=None):
    server = Server(name=name, public_key=PUBLIC_KEY, private_key=PRIVATE_KEY, listen_port=51820,
                    ipv4_address=ipv4, ipv6_address=ipv6, dns_primary=dns_primary,
                    dns_secondary=dns_secondary, endpoint="vpn.example.com")
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


async def make_peer(db, server_id, name="alice", **kwargs):
    peer = Peer(server_id=server_id, name=name, public_key=PUBLIC_KEY, private_key=PRIVATE_KEY,
                preshared_key=kwargs.pop("preshared_key", "C" * 43 + "="),
                ipv4_address=kwargs.pop("ipv4_address", "10.8.0.2"),
                ipv6_address=kwargs.pop("ipv6_address", "fd00:8::2"),
                **kwargs)
    db.add(peer)
    await db.commit()
    await db.refresh(peer)
    return peer


# ===========================================================================
# migrate_peer
# ===========================================================================

class TestMigratePeer:
    async def test_should_reassign_addresses_and_dns_when_moving_peer(self, service, db_session):
        source = await make_server(db_session, "tokyo", dns_primary="1.1.1.1")
        target = await make_server(db_session, "osaka", ipv4="10.9.0.1/24", ipv6="fd00:9::1/64",
                                   dns_primary="9.9.9.9", dns_secondary="149.112.112.112")
        peer = await make_peer(db_session, source.id, dns_primary="8.8.8.8")

        with patch("app.services.migration.event_bus.publish", new=AsyncMock()) as publish:
            result = await service.migrate_peer(db_session, peer.id, target.id, user_id=7)

        assert result["success"] is True
        assert result["peer_id"] == peer.id
        assert result["source_server"] == {"id": source.id, "name": "tokyo"}
        assert result["target_server"] == {"id": target.id, "name": "osaka"}
        assert result["old_configuration"] == {"ipv4_address": "10.8.0.2",
                                               "ipv6_address": "fd00:8::2"}
        assert result["new_configuration"] == {
            "ipv4_address": "10.9.0.2/24",
            "ipv6_address": "fd00:9::2/64",
            "dns_primary": "9.9.9.9",
            "dns_secondary": "149.112.112.112",
        }

        await db_session.refresh(peer)
        assert peer.server_id == target.id
        # key material must never change during migration
        assert (peer.public_key, peer.private_key, peer.preshared_key) == (
            PUBLIC_KEY, PRIVATE_KEY, "C" * 43 + "=",
        )

        publish.assert_awaited_once()
        payload = publish.await_args.args[3]
        assert payload["peer_name"] == "alice"
        assert payload["source_server_name"] == "tokyo"
        assert payload["new_ipv4"] == "10.9.0.2/24"
        assert payload["custom_config"] is False

    async def test_should_apply_custom_configuration(self, service, db_session):
        source = await make_server(db_session, "tokyo")
        target = await make_server(db_session, "osaka", ipv4="10.9.0.1/24", ipv6="fd00:9::1/64")
        peer = await make_peer(db_session, source.id, ipv4_allowed_ips="0.0.0.0/0")

        result = await service.migrate_peer(
            db_session, peer.id, target.id, user_id=1,
            custom_config={
                "ipv4_address": "10.9.0.42/24",
                "ipv6_address": "fd00:9::42/64",
                "dns_primary": "208.67.222.222",
                "dns_secondary": "208.67.220.220",
                "ipv4_allowed_ips": "192.168.0.0/16",
                "ipv6_allowed_ips": "fd00:1::/64",
                "persistent_keepalive": 15,
            },
        )

        await db_session.refresh(peer)
        assert result["new_configuration"] == {
            "ipv4_address": "10.9.0.42/24",
            "ipv6_address": "fd00:9::42/64",
            "dns_primary": "208.67.222.222",
            "dns_secondary": "208.67.220.220",
        }
        assert peer.ipv4_allowed_ips == "192.168.0.0/16"
        assert peer.ipv6_allowed_ips == "fd00:1::/64"
        assert peer.persistent_keepalive == 15

    async def test_should_keep_addresses_when_custom_values_are_empty(self, service, db_session):
        source = await make_server(db_session, "tokyo")
        target = await make_server(db_session, "osaka")
        peer = await make_peer(db_session, source.id, ipv4_address="10.8.0.5")

        await service.migrate_peer(db_session, peer.id, target.id, user_id=1,
                                   custom_config={"ipv4_address": "", "ipv6_address": None,
                                                  "persistent_keepalive": 0})

        await db_session.refresh(peer)
        assert peer.ipv4_address == "10.8.0.5"
        assert peer.persistent_keepalive == 25

    async def test_should_raise_when_peer_missing(self, service, db_session):
        target = await make_server(db_session, "osaka")

        with pytest.raises(ValueError, match="Peer not found"):
            await service.migrate_peer(db_session, 999, target.id, user_id=1)

    async def test_should_raise_when_target_server_missing(self, service, db_session):
        source = await make_server(db_session, "tokyo")
        peer = await make_peer(db_session, source.id)

        with pytest.raises(ValueError, match="Target server not found"):
            await service.migrate_peer(db_session, peer.id, 999, user_id=1)

    async def test_should_bulk_migrate_and_report_failures(self, service, db_session):
        source = await make_server(db_session, "tokyo")
        target = await make_server(db_session, "osaka", ipv4="10.9.0.1/24", ipv6="fd00:9::1/64")
        first = await make_peer(db_session, source.id, "alice", ipv4_address="10.8.0.2")
        second = await make_peer(db_session, source.id, "bob", ipv4_address="10.8.0.3")

        result = await service.bulk_migrate_peers(
            db_session, [first.id, second.id, 4242], target.id, user_id=1
        )

        assert result["success"] is False
        assert result["migrated"] == 2
        assert result["failed"] == 1
        assert result["errors"] == [{"peer_id": 4242, "error": "Peer not found"}]
        await db_session.refresh(first)
        await db_session.refresh(second)
        assert {first.server_id, second.server_id} == {target.id}
        assert first.ipv4_address == "10.9.0.2/24"
        assert second.ipv4_address == "10.9.0.3/24"

    async def test_should_report_success_for_complete_bulk_migration(self, service, db_session):
        source = await make_server(db_session, "tokyo")
        target = await make_server(db_session, "osaka")
        peer = await make_peer(db_session, source.id)

        result = await service.bulk_migrate_peers(db_session, [peer.id], target.id, user_id=1)

        assert result["success"] is True
        assert result["failed"] == 0


class TestServiceMetadata:
    def test_should_report_current_version(self, service):
        assert service.get_current_version() == "2.0.0"
        assert MigrationService.version == "2.0.0"

    async def test_should_return_version_when_no_db_bound(self, service):
        assert await service._get_db_version() == "2.0.0"

    def test_should_delegate_migration_checks(self, service):
        assert service.check_migration_needed() is True
        assert service.migrate_peers() == {"migrated": 0, "total": 0,
                                           "errors": ["No database connection"]}


# ===========================================================================
# Legacy module helpers
# ===========================================================================

class TestModuleHelpers:
    def test_should_run_migration_command(self, monkeypatch):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(migration_module.subprocess, "run", run)

        assert migration_module.run_migration("2.0.0") is True
        assert calls == [["python", "migrate.py", "2.0.0"]]

    def test_should_report_failed_migration_command(self, monkeypatch):
        monkeypatch.setattr(migration_module.subprocess, "run",
                            lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", "boom"))

        assert migration_module.run_migration("2.0.0") is False

    def test_should_report_failed_migration_when_subprocess_raises(self, monkeypatch):
        def run(argv, **kwargs):
            raise OSError("python missing")

        monkeypatch.setattr(migration_module.subprocess, "run", run)

        assert migration_module.run_migration("2.0.0") is False

    def test_should_detect_migration_needed(self):
        assert migration_module.check_migration_needed() is True

    @pytest.mark.parametrize("version", ["1.0.0", "2.10.3", "0.0.1"])
    def test_should_accept_semver_versions(self, version):
        assert migration_module.validate_migration_version(version) == (True, None)
        assert migration_module.is_valid_version(version) is True

    @pytest.mark.parametrize("version", ["2.0", "2.0.0.1", "two.0.0", "2.0.x"])
    def test_should_reject_malformed_versions(self, version):
        valid, message = migration_module.validate_migration_version(version)
        assert valid is False
        assert message in ("Version must be in format X.Y.Z", "Version parts must be numeric")
        assert migration_module.is_valid_version(version) is False

    def test_should_migrate_peer_list_when_db_present(self, monkeypatch):
        monkeypatch.setattr(migration_module, "db", object())

        assert migration_module.migrate_peers() == {"migrated": 0, "total": 0, "errors": []}
        assert migration_module.migrate_peers_empty() == {"migrated": 0, "total": 0, "errors": []}

    def test_should_upgrade_configuration_dictionary(self):
        migrated = migration_module.migrate_config(
            {"settings": {"listen_port": 51900, "interface": "wg3"}}
        )

        assert migrated == {
            "version": "2.0.0",
            "settings": {"listen_port": 51900, "interface": "wg3"},
            "migrated_at": "2024-01-01T00:00:00Z",
        }

    def test_should_default_settings_when_config_has_none(self):
        assert migration_module.migrate_config({})["settings"] == {}

    def test_should_read_config_from_file(self, tmp_path, monkeypatch):
        path = tmp_path / "config.json"
        path.write_text("{}")
        monkeypatch.setattr(migration_module.subprocess, "run",
                            lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "{}", ""))

        migrated = migration_module.migrate_config(str(path))

        assert migrated["settings"] == {"listen_port": 51820, "interface": "wg0"}

    def test_should_fail_config_migration_when_file_unreadable(self, monkeypatch):
        monkeypatch.setattr(migration_module.subprocess, "run",
                            lambda argv, **kw: subprocess.CompletedProcess(argv, 2, "", "missing"))

        assert migration_module.migrate_config("/nope/config.json") is False

    def test_should_fail_config_migration_when_subprocess_raises(self, monkeypatch):
        def run(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 5)

        monkeypatch.setattr(migration_module.subprocess, "run", run)

        assert migration_module.migrate_config("/slow/config.json") is False
        assert migration_module.migrate_config_error({}) is False

    def test_should_export_data_as_dict_or_json(self):
        import json

        exported = migration_module.export_data()
        assert exported == {"format": "json", "data": {"servers": [], "peers": []}}

        as_json = migration_module.export_data_json()
        assert as_json == exported

        text = migration_module.export_data(as_json=True)
        assert json.loads(text) == exported

        assert migration_module.export_data("xml") == {"format": "xml", "data": {}}

    def test_should_export_rows_when_db_is_bound(self, monkeypatch):
        class Db:
            def execute(self, statement):
                class Result:
                    def fetchall(self):
                        return [{"id": 1}]

                return Result()

        monkeypatch.setattr(migration_module, "db", Db())

        assert migration_module.export_data()["data"]["servers"] == [{"id": 1}]
        assert '"peers": [{"id": 1}]' in migration_module.export_data(as_json=True)

    def test_should_fall_back_to_empty_export_when_query_fails(self, monkeypatch):
        class Db:
            def execute(self, statement):
                raise RuntimeError("db down")

        monkeypatch.setattr(migration_module, "db", Db())

        assert migration_module.export_data()["data"] == {"servers": [], "peers": []}
        assert '"servers": []' in migration_module.export_data(as_json=True)

    def test_should_import_data_only_with_servers_and_peers(self):
        assert migration_module.import_data({"servers": [], "peers": []}) is True
        assert migration_module.import_data({"servers": []}) is False

    def test_should_import_json_strings(self):
        assert migration_module.import_data_json('{"servers": [], "peers": []}') is True
        assert migration_module.import_data_json('{"servers": []}') is False
        assert migration_module.import_data_json("not json") is False

    def test_should_build_backup_path(self):
        path = migration_module.create_backup("/backups")

        assert path.startswith("/backups/backup_")
        assert path.endswith(".tar.gz")

    def test_should_restore_backup(self):
        assert migration_module.restore_backup("/backups/backup_1.tar.gz") is True

    def test_should_rollback_using_subprocess(self, monkeypatch):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(migration_module.subprocess, "run", run)

        assert migration_module.rollback_migration("1.0.0") is True
        assert calls == [["python", "rollback.py", "1.0.0"]]

    def test_should_report_failed_rollback(self, monkeypatch):
        monkeypatch.setattr(migration_module.subprocess, "run",
                            lambda argv, **kw: subprocess.CompletedProcess(argv, 3, "", "nope"))

        assert migration_module.rollback_migration("1.0.0") is False

    def test_should_report_rollback_exception(self, monkeypatch):
        def run(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 5)

        monkeypatch.setattr(migration_module.subprocess, "run", run)

        assert migration_module.rollback_migration("1.0.0") is False
        assert migration_module.rollback_migration_error("1.0.0") is False
