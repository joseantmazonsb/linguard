"""Tests for BounceServerService: routing configuration and validation rules."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.peer import Peer
from app.models.server import Server
from app.services.bounce_routing import BounceServerService


def _server(server_id, name, *, is_bounce=False, bounce_via=None, endpoint="vpn.example.com"):
    return Server(
        id=server_id,
        name=name,
        public_key=f"pk-{server_id}-" + "a" * 30,
        private_key="b" * 43 + "=",
        listen_port=51820 + server_id,
        endpoint=endpoint,
        ipv4_address=f"10.10.{server_id}.0/24",
        ipv6_address=f"fd00:{server_id}::/64",
        is_bounce_server=is_bounce,
        bounce_via_server_id=bounce_via,
    )


@pytest.fixture
def service():
    return BounceServerService()


class TestConfigureBounceRouting:
    async def test_should_point_peer_at_bounce_server(self, service, db_session):
        target = _server(1, "target")
        bounce = _server(2, "bounce", is_bounce=True, endpoint="bounce.example.com")
        db_session.add_all([target, bounce])
        await db_session.commit()
        peer = Peer(
            id=10,
            server_id=1,
            name="phone",
            public_key="peer-pk",
            private_key="peer-sk",
            preshared_key="psk",
            ipv4_address="10.10.1.5",
            ipv6_address="fd00:1::5",
        )

        config = await service.configure_bounce_routing(db_session, peer, target, bounce)

        assert config["peer_config"]["server_endpoint"] == "bounce.example.com"
        assert config["peer_config"]["server_port"] == bounce.listen_port
        assert config["peer_config"]["server_public_key"] == bounce.public_key

    async def test_should_route_allowed_ips_to_target_subnets(self, service, db_session):
        target = _server(1, "target")
        bounce = _server(2, "bounce", is_bounce=True)
        db_session.add_all([target, bounce])
        await db_session.commit()
        peer = Peer(
            id=10, server_id=1, name="phone", public_key="pk", private_key="sk",
            ipv4_address="10.10.1.5", ipv6_address="fd00:1::5",
        )

        config = await service.configure_bounce_routing(db_session, peer, target, bounce)

        assert config["peer_config"]["allowed_ips"] == "10.10.1.0/24, fd00:1::/64"

    async def test_should_expose_peer_keys_to_bounce_and_target(self, service, db_session):
        target = _server(1, "target")
        bounce = _server(2, "bounce", is_bounce=True)
        db_session.add_all([target, bounce])
        await db_session.commit()
        peer = Peer(
            id=10, server_id=1, name="phone", public_key="peer-pk", private_key="sk",
            preshared_key="psk", ipv4_address="10.10.1.5", ipv6_address="fd00:1::5",
        )

        config = await service.configure_bounce_routing(db_session, peer, target, bounce)

        assert config["bounce_peer_config"] == {
            "public_key": "peer-pk",
            "allowed_ips": "10.10.1.5, fd00:1::5",
            "preshared_key": "psk",
        }
        assert config["target_peer_config"]["public_key"] == bounce.public_key
        assert (
            config["target_peer_config"]["endpoint"]
            == f"{bounce.endpoint}:{bounce.listen_port}"
        )


class TestValidateBounceServer:
    async def test_should_reject_bouncing_through_itself(self, service, db_session):
        assert await service.validate_bounce_server(db_session, 1, 1) is False

    async def test_should_reject_missing_bounce_server(self, service, db_session):
        assert await service.validate_bounce_server(db_session, 1, 99) is False

    async def test_should_reject_server_not_flagged_as_bounce(self, service, db_session):
        db_session.add(_server(2, "plain"))
        await db_session.commit()

        assert await service.validate_bounce_server(db_session, 1, 2) is False

    async def test_should_accept_valid_bounce_chain(self, service, db_session):
        db_session.add(_server(1, "target"))
        db_session.add(_server(2, "bounce", is_bounce=True))
        await db_session.commit()

        assert await service.validate_bounce_server(db_session, 1, 2) is True

    async def test_should_reject_direct_circular_dependency(self, service, db_session):
        db_session.add(_server(1, "target"))
        db_session.add(_server(2, "bounce", is_bounce=True, bounce_via=1))
        await db_session.commit()

        assert await service.validate_bounce_server(db_session, 1, 2) is False

    async def test_should_reject_indirect_cycle(self, service, db_session):
        db_session.add(_server(1, "target"))
        db_session.add(_server(3, "bounce-b", is_bounce=True, bounce_via=1))
        await db_session.flush()
        db_session.add(_server(2, "bounce-a", is_bounce=True, bounce_via=3))
        await db_session.commit()

        assert await service.validate_bounce_server(db_session, 1, 2) is False

    async def test_should_accept_linear_bounce_chain(self, service, db_session):
        db_session.add(_server(1, "target"))
        db_session.add(_server(3, "entry", is_bounce=True))
        await db_session.flush()
        db_session.add(_server(2, "middle", is_bounce=True, bounce_via=3))
        await db_session.commit()

        assert await service.validate_bounce_server(db_session, 1, 2) is True

    async def test_should_reject_bounce_reference_to_missing_server(
        self, service, db_session
    ):
        db_session.add(_server(1, "target"))
        await db_session.commit()

        with pytest.raises(IntegrityError):
            db_session.add(_server(2, "bounce", is_bounce=True, bounce_via=42))
            await db_session.commit()


class TestGenerateAllowedIps:
    def test_should_join_peer_ips_and_subnets(self, service):
        result = service.generate_bounce_allowed_ips(
            ["10.0.0.2/32", "fd00::2/128"], ["192.168.0.0/24"]
        )

        assert result == "10.0.0.2/32, fd00::2/128, 192.168.0.0/24"

    def test_should_return_empty_string_when_no_inputs(self, service):
        assert service.generate_bounce_allowed_ips([], []) == ""
