"""Tests for ``app.services.dns_hierarchy``.

The important behaviour is the precedence rule Peer > Server > Global, which is
exercised against the real database, plus the legacy DNS-server helpers and the
DNS config file writer.
"""

import json
import subprocess
from types import SimpleNamespace

import pytest

from app.models.peer import Peer
from app.models.server import Server
from app.models.settings import GlobalSettings
from app.services import dns_hierarchy as dns_module
from app.services.dns_hierarchy import (
    DNSHierarchyConfig,
    DNSHierarchyService,
    get_dns_servers_for_test,
    get_peer_ips_for_test,
    resolve_dns,
    update_dns,
    validate_dns_server,
)


async def set_global_dns(db, primary="1.1.1.1", secondary="1.0.0.1"):
    row = (await _scalar(db, GlobalSettings))
    if row is None:
        row = GlobalSettings(
            secret_key="k" * 32, backup_dir="./backups", plugins_directory="./plugins",
            log_path="./linguard.log", dns_primary=primary, dns_secondary=secondary,
        )
        db.add(row)
    else:
        row.dns_primary = primary
        row.dns_secondary = secondary
    await db.commit()
    return row


async def _scalar(db, model):
    from sqlalchemy import select

    return (await db.execute(select(model))).scalar_one_or_none()


async def make_server(db, name="srv", dns_primary=None, dns_secondary=None):
    server = Server(name=name, public_key="a" * 44, private_key="b" * 44, listen_port=51820,
                    ipv4_address="10.8.0.1/24", dns_primary=dns_primary,
                    dns_secondary=dns_secondary)
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


async def make_peer(db, server_id, name="peer", dns_primary=None, dns_secondary=None):
    peer = Peer(server_id=server_id, name=name, public_key="c" * 44, private_key="d" * 44,
                ipv4_address="10.8.0.2", dns_primary=dns_primary, dns_secondary=dns_secondary)
    db.add(peer)
    await db.commit()
    await db.refresh(peer)
    return peer


# ===========================================================================
# Precedence
# ===========================================================================

class TestEffectiveDns:
    async def test_should_return_global_dns_when_nothing_overrides_it(self, db_session):
        await set_global_dns(db_session, "1.1.1.1", "1.0.0.1")

        result = await DNSHierarchyService().get_effective_dns(db_session)

        assert result == ("1.1.1.1", "1.0.0.1")

    async def test_should_prefer_server_dns_over_global(self, db_session):
        await set_global_dns(db_session)
        server = await make_server(db_session, dns_primary="10.8.0.1", dns_secondary="10.9.0.1")

        assert await DNSHierarchyService().get_effective_dns(db_session, server_id=server.id) == (
            "10.8.0.1", "10.9.0.1",
        )

    async def test_should_keep_global_secondary_when_server_only_sets_primary(self, db_session):
        await set_global_dns(db_session, "1.1.1.1", "1.0.0.1")
        server = await make_server(db_session, dns_primary="10.8.0.1")

        assert await DNSHierarchyService().get_effective_dns(db_session, server_id=server.id) == (
            "10.8.0.1", "1.0.0.1",
        )

    async def test_should_prefer_peer_dns_over_server_and_global(self, db_session):
        await set_global_dns(db_session)
        server = await make_server(db_session, dns_primary="10.8.0.1", dns_secondary="10.9.0.1")
        peer = await make_peer(db_session, server.id, dns_primary="8.8.8.8", dns_secondary="8.8.4.4")

        service = DNSHierarchyService()

        assert await service.get_effective_dns(db_session, peer_id=peer.id, server_id=server.id) == (
            "8.8.8.8", "8.8.4.4",
        )
        assert await service.resolve_dns_for_peer(db_session, peer.id) == ("8.8.8.8", "8.8.4.4")

    async def test_should_inherit_when_peer_has_no_dns_of_its_own(self, db_session):
        await set_global_dns(db_session)
        server = await make_server(db_session, dns_primary="10.8.0.1")
        peer = await make_peer(db_session, server.id)

        assert await DNSHierarchyService().resolve_dns_for_peer(db_session, peer.id) == (
            "10.8.0.1", "1.0.0.1",
        )

    async def test_should_return_nothing_when_no_settings_and_no_overrides(self, db_session):
        assert await DNSHierarchyService().get_effective_dns(db_session) == (None, None)

    async def test_should_ignore_unknown_server_and_peer_ids(self, db_session):
        await set_global_dns(db_session, "1.1.1.1", "1.0.0.1")

        assert await DNSHierarchyService().get_effective_dns(
            db_session, peer_id=987, server_id=654
        ) == ("1.1.1.1", "1.0.0.1")

    async def test_should_apply_direct_overrides_last(self, db_session):
        await set_global_dns(db_session)
        server = await make_server(db_session, dns_primary="10.8.0.1")
        peer = await make_peer(db_session, server.id, dns_primary="8.8.8.8")

        result = await DNSHierarchyService().get_effective_dns(
            db_session, peer_id=peer.id, server_id=server.id,
            peer_override_primary="208.67.222.222", peer_override_secondary="208.67.220.220",
        )

        assert result == ("208.67.222.222", "208.67.220.220")

    async def test_should_allow_clearing_dns_with_empty_override(self, db_session):
        await set_global_dns(db_session)

        result = await DNSHierarchyService().get_effective_dns(
            db_session, peer_override_primary="", peer_override_secondary=None
        )

        assert result == ("", "1.0.0.1")

    async def test_should_return_server_defaults_for_new_peers(self, db_session):
        await set_global_dns(db_session)
        server = await make_server(db_session, dns_primary="10.8.0.1")

        assert await DNSHierarchyService().get_default_dns_for_server(db_session, server.id) == (
            "10.8.0.1", "1.0.0.1",
        )

    async def test_should_return_global_defaults_for_new_server(self, db_session):
        await set_global_dns(db_session, "9.9.9.9", "149.112.112.112")

        assert await DNSHierarchyService().get_default_dns_for_new_server(db_session) == (
            "9.9.9.9", "149.112.112.112",
        )


# ===========================================================================
# Legacy helpers
# ===========================================================================

class TestDnsServerHelpers:
    def test_should_validate_complete_server_definition(self):
        assert validate_dns_server({"name": "cf", "ip": "1.1.1.1", "port": 53}) is True

    @pytest.mark.parametrize(
        "server",
        [
            {"ip": "1.1.1.1", "port": 53},
            {"name": "cf", "port": 53},
            {"name": "cf", "ip": "1.1.1.1"},
            {"name": "cf", "ip": "1.1.1.1", "port": 0},
        ],
    )
    def test_should_reject_incomplete_server_definition(self, server):
        assert validate_dns_server(server) is False

    def test_should_degrade_to_empty_list_when_storage_unavailable(self, caplog):
        # The legacy helpers talk to a module level sqlite session that has no
        # dns_server table, so they must swallow the failure.
        assert dns_module.get_dns_servers() == []
        assert dns_module.get_dns_config() == {}
        assert dns_module.get_peer_ips(1) == []

    @pytest.mark.parametrize(
        "func, args",
        [
            (dns_module.add_dns_server, ({"name": "cf", "ip": "1.1.1.1", "port": 53},)),
            (dns_module.remove_dns_server, (1,)),
            (dns_module.update_dns_server, (1, {"name": "cf", "ip": "1.1.1.1", "port": 53})),
            (dns_module.set_dns_config, ({"dns_primary": "1.1.1.1"},)),
        ],
    )
    def test_should_report_failure_when_storage_unavailable(self, func, args):
        assert not func(*args)

    def test_should_expose_test_fixtures(self):
        assert [s["ip"] for s in get_dns_servers_for_test()] == ["8.8.8.8", "1.1.1.1"]
        assert get_peer_ips_for_test() == ["192.168.1.10", "192.168.1.11"]

    def test_should_delegate_service_wrappers(self, monkeypatch):
        service = DNSHierarchyService()
        calls = []

        monkeypatch.setattr(dns_module, "get_dns_servers", lambda: [{"name": "x"}])
        monkeypatch.setattr(dns_module, "add_dns_server", lambda s: 1)
        monkeypatch.setattr(dns_module, "remove_dns_server", lambda i: 1)
        monkeypatch.setattr(dns_module, "update_dns_server", lambda i, s: 0)
        monkeypatch.setattr(dns_module, "get_dns_config", lambda: {"dns_domain": "lan"})
        monkeypatch.setattr(dns_module, "set_dns_config", lambda c: calls.append(c) or True)
        monkeypatch.setattr(dns_module, "resolve_dns", lambda h: "1.2.3.4")
        monkeypatch.setattr(dns_module, "update_dns", lambda p=None: True)

        assert service.get_dns_servers() == [{"name": "x"}]
        assert service.add_dns_server({"name": "x"}) is True
        assert service.remove_dns_server(1) is True
        assert service.update_dns_server(1, {"name": "x"}) is False
        assert service.validate_dns_server({"name": "x", "ip": "1.1.1.1", "port": 53}) is True
        assert service.get_dns_config() == {"dns_domain": "lan"}
        assert service.set_dns_config({"dns_primary": "1.1.1.1"}) is True
        assert service.resolve_dns("host") == "1.2.3.4"
        assert service.update_dns([{"ip": "10.8.0.2"}]) is True
        assert calls == [{"dns_primary": "1.1.1.1"}]


class TestResolveDns:
    def _stub(self, monkeypatch, returncode=0, stdout=b""):
        def run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, returncode, stdout, b"")

        monkeypatch.setattr(dns_module.subprocess, "run", run)

    def test_should_return_first_ipv4_address_from_nslookup(self, monkeypatch):
        self._stub(monkeypatch, stdout=(
            b"Server:  8.8.8.8\nAddress: 8.8.8.8#53\n\n"
            b"Name:    vpn.example.com\nAddress: 203.0.113.7\n"
        ))

        assert resolve_dns("vpn.example.com") == "203.0.113.7"

    def test_should_return_ipv6_address_when_present(self, monkeypatch):
        self._stub(monkeypatch, stdout=b"Name: vpn.example.com\nAddress: 2001:db8::7\n")

        assert resolve_dns("vpn.example.com") == "2001:db8::7"

    def test_should_return_none_when_lookup_fails(self, monkeypatch):
        self._stub(monkeypatch, returncode=1)

        assert resolve_dns("nope.invalid") is None

    def test_should_return_none_when_subprocess_raises(self, monkeypatch):
        def run(argv, **kwargs):
            raise OSError("nslookup missing")

        monkeypatch.setattr(dns_module.subprocess, "run", run)

        assert resolve_dns("host") is None


class TestUpdateDnsConfigFile:
    @pytest.fixture
    def config_file(self, tmp_path, monkeypatch):
        target = tmp_path / "etc" / "dns.json"
        fake_config = SimpleNamespace(
            dns_servers=["10.8.0.1", "1.1.1.1"],
            dns_domain="vpn.lan",
            dns_config_path=str(target),
            wireguard_config="/etc/wireguard/wg0.conf",
        )
        monkeypatch.setattr(dns_module, "config", fake_config)
        return target

    def test_should_write_peer_ips_and_dns_servers_to_config(self, config_file):
        assert update_dns([{"ip": "10.8.0.2"}, {"ip": "10.8.0.3"}, {"name": "no-ip"}]) is True

        data = json.loads(config_file.read_text())
        assert data["dns_servers"] == ["10.8.0.1", "1.1.1.1"]
        assert data["dns_domain"] == "vpn.lan"
        assert data["peers"] == ["10.8.0.2", "10.8.0.3"]

    def test_should_write_empty_peer_list_when_none_given(self, config_file):
        assert update_dns() is True
        assert json.loads(config_file.read_text())["peers"] == []

    def test_should_report_failure_when_file_cannot_be_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr(dns_module, "config", SimpleNamespace(
            dns_servers=[], dns_domain="x", dns_config_path="/proc/forbidden/dns.json",
            wireguard_config="/etc/wireguard/wg0.conf",
        ))

        assert update_dns() is False

    def test_should_generate_config_dictionary(self, config_file):
        assert dns_module.generate_dns_config() == {
            "dns_servers": ["10.8.0.1", "1.1.1.1"],
            "dns_domain": "vpn.lan",
            "wireguard_config": "/etc/wireguard/wg0.conf",
            "dns_config_path": str(config_file),
        }

    def test_should_validate_json_config_through_helper(self, config_file, monkeypatch):
        config_file.parent.mkdir(parents=True)
        config_file.write_text('{"dns_servers": []}')
        monkeypatch.setattr(dns_module.subprocess, "run",
                            lambda argv, **kw: subprocess.CompletedProcess(argv, 0, b"", b""))

        assert dns_module.is_dns_valid(str(config_file)) is True

    def test_should_report_invalid_dns_config(self, config_file, monkeypatch):
        monkeypatch.setattr(dns_module.subprocess, "run",
                            lambda argv, **kw: subprocess.CompletedProcess(argv, 1, b"", b""))

        assert dns_module.is_dns_valid(str(config_file)) is False


class TestDnsHierarchyConfig:
    def test_should_return_defaults(self):
        config = DNSHierarchyConfig.get_default_config()

        assert config.dns_servers == []
        assert config.dns_domain == "example.com"
        assert config.wireguard_config == "/etc/wireguard/wg0.conf"
        assert config.dns_config_path == "/etc/dns/config.json"

    def test_should_load_existing_file_with_defaults(self, tmp_path):
        path = tmp_path / "dns.json"
        path.write_text("{}")

        assert DNSHierarchyConfig.from_file(path).dns_domain == "example.com"

    def test_should_raise_when_config_file_is_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="DNS hierarchy config file not found"):
            DNSHierarchyConfig.from_file(tmp_path / "missing.json")

    def test_should_serialize_configuration(self):
        data = DNSHierarchyConfig(dns_servers=["1.1.1.1"]).model_dump()

        assert data["dns_servers"] == ["1.1.1.1"]
        assert set(data) == {"dns_servers", "dns_domain", "wireguard_config", "dns_config_path"}


class TestLegacyStorage:
    """Exercise the legacy helpers against a real (temporary) sqlite session."""

    @pytest.fixture
    def legacy_db(self, tmp_path, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE dns_server (id INTEGER PRIMARY KEY, name TEXT, ip TEXT, "
                "port INTEGER, enabled INTEGER)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE dns_config (dns_primary TEXT, dns_secondary TEXT, dns_domain TEXT)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE peer (id INTEGER PRIMARY KEY, server_id INTEGER, "
                "ipv4_address TEXT, ipv6_address TEXT)"
            )
        session = sessionmaker(bind=engine)()
        monkeypatch.setattr(dns_module, "db", session)
        yield session
        session.close()
        engine.dispose()

    def test_should_insert_read_update_and_delete_dns_server(self, legacy_db):
        assert dns_module.add_dns_server({"name": "cf", "ip": "1.1.1.1", "port": 53}) == 1
        servers = dns_module.get_dns_servers()
        assert [(s["name"], s["ip"], s["port"]) for s in servers] == [("cf", "1.1.1.1", 53)]

        assert dns_module.update_dns_server(1, {"name": "cloudflare", "ip": "1.0.0.1", "port": 53}) == 1
        assert dns_module.get_dns_servers()[0]["name"] == "cloudflare"

        assert dns_module.remove_dns_server(1) == 1
        assert dns_module.get_dns_servers() == []

    def test_should_store_and_read_dns_config(self, legacy_db):
        assert dns_module.get_dns_config() == {}

        assert dns_module.set_dns_config(
            {"dns_primary": "1.1.1.1", "dns_secondary": "1.0.0.1", "dns_domain": "vpn.lan"}
        ) is True

        assert dns_module.get_dns_config()["dns_domain"] == "vpn.lan"

    def test_should_list_peer_addresses_for_a_server(self, legacy_db):
        with legacy_db.get_bind().begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO peer (server_id, ipv4_address, ipv6_address) VALUES "
                "(1, '10.8.0.2', 'fd00::2'), (1, NULL, 'fd00::3'), (2, '10.9.0.2', NULL)"
            )

        assert dns_module.get_peer_ips(1) == ["10.8.0.2", "fd00::2", "fd00::3"]


class TestConfigFromDirectory:
    def test_should_return_defaults_when_path_is_a_directory(self, tmp_path):
        directory = tmp_path / "configs"
        directory.mkdir()

        config = DNSHierarchyConfig.from_file(directory)

        assert config.dns_domain == "example.com"
        assert config.dns_servers == []
