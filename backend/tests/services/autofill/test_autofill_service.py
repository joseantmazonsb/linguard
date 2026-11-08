"""Tests for ``app.services.autofill``.

``AutoFillService`` derives defaults for the create-server/create-peer forms from
the current database contents; the legacy ``AutofillService`` helpers manage the
``autofill_rule`` table and apply rules to incoming form data.
"""

import pytest
from sqlalchemy import select

from app.models.peer import Peer
from app.models.server import Server
from app.models.settings import GlobalSettings
from app.services import autofill as autofill_module
from app.services.autofill import (
    AutoFillService,
    AutofillConfig,
    AutofillRule,
    AutofillService,
    apply_autofill,
    validate_rule,
)
from app.services.dns_hierarchy import DNSHierarchyService
from app.services.ip_management import IPManagementService

PRIVATE_KEY = "A" * 43 + "="
PUBLIC_KEY = "B" * 43 + "="
PSK = "C" * 43 + "="


class StubWireGuard:
    def __init__(self):
        self.keypair_calls = 0
        self.psk_calls = 0

    def generate_keypair(self):
        self.keypair_calls += 1
        return PRIVATE_KEY, PUBLIC_KEY

    def generate_preshared_key(self):
        self.psk_calls += 1
        return PSK


@pytest.fixture
def wireguard():
    return StubWireGuard()


@pytest.fixture
def autofill(wireguard):
    return AutoFillService(
        ip_management_service=IPManagementService(),
        dns_hierarchy_service=DNSHierarchyService(),
        wireguard_service=wireguard,
    )


async def set_global_dns(db, primary="1.1.1.1", secondary="1.0.0.1"):
    row = (await db.execute(select(GlobalSettings))).scalar_one()
    row.dns_primary = primary
    row.dns_secondary = secondary
    await db.commit()


async def make_server(db, name, interface=None, listen_port=51820, ipv4=None, ipv6=None,
                      dns_primary=None, dns_secondary=None):
    server = Server(name=name, interface=interface, public_key=PUBLIC_KEY, private_key=PRIVATE_KEY,
                    listen_port=listen_port, ipv4_address=ipv4, ipv6_address=ipv6,
                    dns_primary=dns_primary, dns_secondary=dns_secondary)
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


# ===========================================================================
# Server defaults
# ===========================================================================

class TestServerDefaults:
    async def test_should_suggest_first_server_values_on_empty_database(
            self, autofill, wireguard, db_session, seeded_db):
        await set_global_dns(db_session)

        defaults = await autofill.get_server_defaults(db_session)

        assert defaults == {
            "interface": "wg0",
            "listen_port": 51820,
            "ipv4_address": "10.0.0.1/24",
            "ipv6_address": "fd00::1/64",
            "dns_primary": "1.1.1.1",
            "dns_secondary": "1.0.0.1",
            "private_key": PRIVATE_KEY,
            "public_key": PUBLIC_KEY,
            "is_bounce_server": False,
            "enabled": True,
        }
        assert wireguard.keypair_calls == 1

    async def test_should_increment_port_and_interface_for_existing_servers(
            self, autofill, db_session, seeded_db):
        await set_global_dns(db_session)
        await make_server(db_session, "one", interface="wg0", listen_port=51820, ipv4="10.0.0.1/24",
                          ipv6="fd00::1/64")
        await make_server(db_session, "two", interface="wg1", listen_port=51821, ipv4="10.0.1.1/24",
                          ipv6="fd00:0:0:1::1/64")

        defaults = await autofill.get_server_defaults(db_session)

        assert defaults["interface"] == "wg2"
        assert defaults["listen_port"] == 51822
        assert defaults["ipv4_address"] == "10.0.2.1/24"
        assert defaults["ipv6_address"] == "fd00:0:0:2::1/64"

    async def test_should_reset_port_to_default_when_existing_ports_are_low(
            self, autofill, db_session, seeded_db):
        await set_global_dns(db_session)
        await make_server(db_session, "legacy", listen_port=1234)

        defaults = await autofill.get_server_defaults(db_session)

        assert defaults["listen_port"] == 51820

    async def test_should_ignore_server_specific_dns(self, autofill, db_session, seeded_db):
        await set_global_dns(db_session, "9.9.9.9", "149.112.112.112")
        await make_server(db_session, "one", dns_primary="10.0.0.53")

        defaults = await autofill.get_server_defaults(db_session)

        assert (defaults["dns_primary"], defaults["dns_secondary"]) == ("9.9.9.9", "149.112.112.112")


# ===========================================================================
# Peer defaults
# ===========================================================================

class TestPeerDefaults:
    async def test_should_suggest_first_peer_values(self, autofill, wireguard, db_session, seeded_db):
        await set_global_dns(db_session)
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/24", ipv6="fd00:8::1/64")

        defaults = await autofill.get_peer_defaults(db_session, server.id)

        assert defaults == {
            "server_id": server.id,
            "ipv4_address": "10.8.0.2/24",
            "ipv6_address": "fd00:8::2/64",
            "ipv4_allowed_ips": "0.0.0.0/0",
            "ipv6_allowed_ips": "::/0",
            "dns_primary": "1.1.1.1",
            "dns_secondary": "1.0.0.1",
            "private_key": PRIVATE_KEY,
            "public_key": PUBLIC_KEY,
            "preshared_key": PSK,
            "persistent_keepalive": 25,
            "enabled": True,
        }
        assert (wireguard.keypair_calls, wireguard.psk_calls) == (1, 1)

    async def test_should_skip_addresses_used_by_existing_peers(self, autofill, db_session, seeded_db):
        await set_global_dns(db_session)
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/24", ipv6="fd00:8::1/64")
        db_session.add(Peer(server_id=server.id, name="alice", public_key=PUBLIC_KEY,
                            private_key=PRIVATE_KEY, ipv4_address="10.8.0.2",
                            ipv6_address="fd00:8::2"))
        await db_session.commit()

        defaults = await autofill.get_peer_defaults(db_session, server.id)

        assert (defaults["ipv4_address"], defaults["ipv6_address"]) == ("10.8.0.3/24", "fd00:8::3/64")

    async def test_should_inherit_server_dns_for_new_peers(self, autofill, db_session, seeded_db):
        await set_global_dns(db_session)
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/24",
                                   dns_primary="10.8.0.53", dns_secondary="10.9.0.53")

        defaults = await autofill.get_peer_defaults(db_session, server.id)

        assert (defaults["dns_primary"], defaults["dns_secondary"]) == ("10.8.0.53", "10.9.0.53")

    async def test_should_return_none_addresses_for_server_without_subnets(
            self, autofill, db_session, seeded_db):
        await set_global_dns(db_session)
        server = await make_server(db_session, "bare")

        defaults = await autofill.get_peer_defaults(db_session, server.id)

        assert defaults["ipv4_address"] is None
        assert defaults["ipv6_address"] is None


# ===========================================================================
# Rule storage (legacy helpers)
# ===========================================================================

class TestRuleStorage:
    @pytest.fixture
    def legacy_db(self, tmp_path, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{tmp_path / 'autofill.db'}")
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE autofill_rule (id INTEGER PRIMARY KEY, field TEXT, \"default\" TEXT, "
                "required INTEGER, pattern TEXT, placeholder TEXT, label TEXT, description TEXT)"
            )
        session = sessionmaker(bind=engine)()
        monkeypatch.setattr(autofill_module, "db", session)
        yield session
        session.close()
        engine.dispose()

    def test_should_add_update_and_remove_rules(self, legacy_db):
        service = AutofillService()

        assert service.add_rule({"field": "listen_port", "default": "51820",
                                 "label": "Listen port"}) == 1
        rules = service.get_rules()
        assert [(r.field, r.default, r.label) for r in rules] == [("listen_port", "51820", "Listen port")]

        assert service.update_rule(1, {"field": "port", "default": "51900"}) == 1
        assert [(r.field, r.default) for r in service.get_rules()] == [("port", "51900")]

        assert service.remove_rule(1) == 1
        assert service.get_rules() == []

    def test_should_reject_invalid_rule_payload(self, legacy_db):
        service = AutofillService()

        assert service.add_rule({"default": "no field"}) == 0
        assert service.update_rule(1, {"default": "no field"}) == 0

    def test_should_fall_back_to_configured_rules_when_storage_unavailable(self, monkeypatch):
        fallback = [AutofillRule(field="listen_port", default="51820")]
        monkeypatch.setattr(autofill_module, "config", AutofillConfig(autofill_rules=fallback))

        assert autofill_module.get_autofill_rules() == fallback
        assert autofill_module.add_autofill_rule({"field": "x", "default": "y"}) == 0
        assert autofill_module.remove_autofill_rule(1) == 0
        assert autofill_module.update_autofill_rule(1, {"field": "x", "default": "y"}) == 0


class TestApplyAutofill:
    @pytest.fixture
    def configured(self, monkeypatch):
        config = AutofillConfig(autofill_rules=[
            AutofillRule(field="listen_port", default="51820"),
            AutofillRule(field="interface", default="wg0"),
            AutofillRule(field="persistent_keepalive", default="25"),
            AutofillRule(field="no_default"),
        ])
        monkeypatch.setattr(autofill_module, "config", config)
        return config

    def test_should_fill_only_missing_fields(self, configured):
        result = apply_autofill({"interface": "wg7", "listen_port": ""})

        assert result == {"interface": "wg7", "listen_port": "51820",
                          "persistent_keepalive": "25"}
        assert "no_default" not in result

    def test_should_not_mutate_original_form_data(self, configured):
        form = {"name": "peer"}

        apply_autofill(form)

        assert form == {"name": "peer"}

    def test_should_accept_rule_dictionaries(self, configured):
        configured.autofill_rules = [{"field": "dns", "default": "1.1.1.1"}]

        assert apply_autofill({}) == {"dns": "1.1.1.1"}

    def test_should_do_nothing_when_autofill_is_disabled(self, configured):
        configured.autofill_enabled = False

        assert apply_autofill({"listen_port": ""}) == {"listen_port": ""}


class TestRuleValidation:
    def test_should_accept_rule_with_field_and_default(self):
        assert validate_rule({"field": "port", "default": "51820"}) is True
        assert validate_rule({"field": "port", "default": None}) is True

    @pytest.mark.parametrize(
        "rule",
        [
            {"default": "51820"},
            {"field": 42, "default": "x"},
            {"field": "port"},
        ],
    )
    def test_should_reject_incomplete_rules(self, rule):
        assert validate_rule(rule) is False

    def test_should_compare_rules_by_serialized_fields(self):
        assert AutofillRule(field="a", default="1") == AutofillRule(field="a", default="1")
        assert not (AutofillRule(field="a", default="1") == AutofillRule(field="a", default="2"))
        assert not (AutofillRule(field="a") == "a")
        assert AutofillRule(field="a").model_dump()["default"] is None


class TestAutofillConfig:
    def test_should_expose_defaults(self):
        config = AutofillConfig.get_default_config()

        assert config.autofill_enabled is True
        assert config.autofill_rules == []
        assert (config.autofill_timeout, config.autofill_retry_count) == (300, 3)

    def test_should_load_existing_file(self, tmp_path):
        path = tmp_path / "autofill.yml"
        path.write_text("autofill_enabled: true")

        assert AutofillConfig.from_file(path).autofill_enabled is True

    def test_should_raise_when_config_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Autofill config file not found"):
            AutofillConfig.from_file(tmp_path / "missing.yml")
