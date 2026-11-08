"""Database-backed tests for ``app.services.ip_management.IPManagementService``.

Allocation rules covered here: the server's own address is reserved, network and
broadcast addresses are never handed out (``hosts()``), peers on *other* servers
do not influence the result, and exhaustion returns ``None``.
"""

import pytest

from app.models.peer import Peer
from app.models.server import Server
from app.services.ip_management import IPManagementService


@pytest.fixture
def service():
    return IPManagementService()


async def make_server(db, name, ipv4=None, ipv6=None):
    server = Server(name=name, public_key="a" * 44, private_key="b" * 44, listen_port=51820,
                    ipv4_address=ipv4, ipv6_address=ipv6)
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


async def make_peer(db, server_id, name, ipv4=None, ipv6=None):
    peer = Peer(server_id=server_id, name=name, public_key="c" * 44, private_key="d" * 44,
                ipv4_address=ipv4, ipv6_address=ipv6)
    db.add(peer)
    await db.commit()
    await db.refresh(peer)
    return peer


class TestNextAvailableIpv4:
    async def test_should_return_first_host_after_server_address(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/24")

        assert await service.get_next_available_ipv4(db_session, server.id) == "10.8.0.2/24"

    async def test_should_skip_addresses_already_used_by_peers(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/24")
        await make_peer(db_session, server.id, "p1", ipv4="10.8.0.2/32")
        await make_peer(db_session, server.id, "p2", ipv4="10.8.0.3")
        await make_peer(db_session, server.id, "p3", ipv4="10.8.0.5/24")

        assert await service.get_next_available_ipv4(db_session, server.id) == "10.8.0.4/24"

    async def test_should_ignore_peers_of_other_servers(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/24")
        other = await make_server(db_session, "osaka", ipv4="10.9.0.1/24")
        await make_peer(db_session, other.id, "remote", ipv4="10.8.0.2")

        assert await service.get_next_available_ipv4(db_session, server.id) == "10.8.0.2/24"

    async def test_should_ignore_peers_without_ipv4_address(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/24")
        await make_peer(db_session, server.id, "v6-only", ipv6="fd00::2")

        assert await service.get_next_available_ipv4(db_session, server.id) == "10.8.0.2/24"

    async def test_should_accept_a_bare_server_address(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv4="192.168.50.1")

        # Bare addresses are treated as /32, whose only host is the server itself
        assert await service.get_next_available_ipv4(db_session, server.id) is None

    async def test_should_return_none_when_subnet_is_exhausted(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/30")
        await make_peer(db_session, server.id, "p1", ipv4="10.8.0.2")

        assert await service.get_next_available_ipv4(db_session, server.id) is None

    async def test_should_return_none_when_server_missing(self, service, db_session):
        assert await service.get_next_available_ipv4(db_session, 404) is None

    async def test_should_return_none_when_server_has_no_ipv4(self, service, db_session):
        server = await make_server(db_session, "tokyo")

        assert await service.get_next_available_ipv4(db_session, server.id) is None

    async def test_should_never_hand_out_network_or_broadcast(self, service, db_session):
        # /29 -> hosts .1 ... .6
        server = await make_server(db_session, "tokyo", ipv4="10.8.0.1/29")
        for index, last in enumerate([2, 3, 4, 5, 6]):
            await make_peer(db_session, server.id, f"p{index}", ipv4=f"10.8.0.{last}")

        assert await service.get_next_available_ipv4(db_session, server.id) is None


class TestNextAvailableIpv6:
    async def test_should_return_first_host_after_server_address(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv6="fd00:8::1/64")

        assert await service.get_next_available_ipv6(db_session, server.id) == "fd00:8::2/64"

    async def test_should_skip_addresses_used_by_peers(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv6="fd00:8::1/64")
        await make_peer(db_session, server.id, "p1", ipv6="fd00:8::2/128")

        assert await service.get_next_available_ipv6(db_session, server.id) == "fd00:8::3/64"

    async def test_should_return_none_when_ipv6_subnet_is_exhausted(self, service, db_session):
        server = await make_server(db_session, "tokyo", ipv6="fd00:8::1/126")
        await make_peer(db_session, server.id, "p1", ipv6="fd00:8::2/128")
        await make_peer(db_session, server.id, "p2", ipv6="fd00:8::3/128")

        assert await service.get_next_available_ipv6(db_session, server.id) is None

    async def test_should_return_none_when_server_missing(self, service, db_session):
        assert await service.get_next_available_ipv6(db_session, 404) is None

    async def test_should_return_none_when_server_has_no_ipv6(self, service, db_session):
        server = await make_server(db_session, "tokyo")

        assert await service.get_next_available_ipv6(db_session, server.id) is None


class TestServerSubnetAllocation:
    async def test_should_allocate_first_free_ipv4_subnet(self, service, db_session):
        assert await service.get_next_server_subnet_ipv4(db_session) == "10.0.0.1/24"

    async def test_should_skip_taken_ipv4_subnets(self, service, db_session):
        await make_server(db_session, "tokyo", ipv4="10.0.0.1/24")
        await make_server(db_session, "osaka", ipv4="10.0.2.1/24")

        assert await service.get_next_server_subnet_ipv4(db_session) == "10.0.1.1/24"

    async def test_should_ignore_servers_without_ipv4(self, service, db_session):
        await make_server(db_session, "no-ip")

        assert await service.get_next_server_subnet_ipv4(db_session) == "10.0.0.1/24"

    async def test_should_allocate_first_free_ipv6_subnet(self, service, db_session):
        assert await service.get_next_server_subnet_ipv6(db_session) == "fd00::1/64"

    async def test_should_skip_taken_ipv6_subnets(self, service, db_session):
        await make_server(db_session, "tokyo", ipv6="fd00::1/64")
        await make_server(db_session, "osaka", ipv6="fd00:0:0:2::1/64")

        assert await service.get_next_server_subnet_ipv6(db_session) == "fd00:0:0:1::1/64"

    async def test_should_ignore_servers_without_ipv6(self, service, db_session):
        await make_server(db_session, "no-v6", ipv4="10.0.0.1/24")

        assert await service.get_next_server_subnet_ipv6(db_session) == "fd00::1/64"


class TestValidation:
    @pytest.mark.parametrize("value", ["10.8.0.1", "10.8.0.1/24", "10.8.0.1/32", "0.0.0.0/0"])
    def test_should_accept_valid_ipv4(self, service, value):
        assert service.validate_ipv4(value) is True

    @pytest.mark.parametrize("value", ["10.8.0.256", "10.8.0.0/33", "fd00::1", "", "10.8.0"])
    def test_should_reject_invalid_ipv4(self, service, value):
        assert service.validate_ipv4(value) is False

    @pytest.mark.parametrize("value", ["fd00::1", "fd00::1/64", "fe80::1/128"])
    def test_should_accept_valid_ipv6(self, service, value):
        assert service.validate_ipv6(value) is True

    @pytest.mark.parametrize("value", ["fd00::/129", "10.8.0.1", "", "gggg::1"])
    def test_should_reject_invalid_ipv6(self, service, value):
        assert service.validate_ipv6(value) is False


class TestModuleHelpers:
    """Pure helpers used by the allocation routines and legacy test shims."""

    def test_should_list_ipv4_hosts_excluding_network_and_broadcast(self):
        from app.services.ip_management import _get_subnet_addresses

        addresses = _get_subnet_addresses("192.168.1.0/24")

        assert addresses[0] == "192.168.1.1"
        assert addresses[-1] == "192.168.1.100"  # capped at 100 entries
        assert "192.168.1.0" not in addresses
        assert "192.168.1.255" not in addresses

    def test_should_generate_link_local_ipv6_hosts(self):
        from app.services.ip_management import _get_subnet_addresses

        assert _get_subnet_addresses("fe80::/64") == [f"fe80::{i}" for i in range(1, 11)]

    def test_should_return_empty_list_for_invalid_cidr(self):
        from app.services.ip_management import _get_subnet_addresses

        assert _get_subnet_addresses("not-a-subnet") == []

    def test_should_increment_last_octet_and_carry(self):
        from app.services.ip_management import _increment_ip

        assert _increment_ip("10.0.0.1") == "10.0.0.2"
        assert _increment_ip("10.0.0.1", increment=5) == "10.0.0.6"
        assert _increment_ip("10.0.0.255") == "10.0.1.0"

    def test_should_leave_ipv6_untouched_when_incrementing(self):
        from app.services.ip_management import _increment_ip

        assert _increment_ip("fd00::1") == "fd00::1"

    @pytest.mark.parametrize(
        "ip, server_ip, expected",
        [
            (None, None, False),
            ("", None, False),
            ("   ", None, False),
            ("10.8.0.1", "10.8.0.1", False),
            ("10.8.0.2", "10.8.0.1", True),
        ],
    )
    def test_should_decide_availability(self, ip, server_ip, expected):
        from app.services.ip_management import _is_ip_available

        assert _is_ip_available(ip, server_ip) is expected

    def test_should_expose_legacy_test_shims(self):
        from app.services.ip_management import DBMock, SubprocessMock

        result = SubprocessMock().run(["ip", "route"])
        assert (result.returncode, result.stdout) == (0, b"192.168.1.100")

        executed = DBMock().execute()
        assert executed.scalars().all() == []
        assert executed.scalars().first() is None
        assert executed.fetchall() == []

    def test_should_suggest_ip_from_supplied_subnet(self):
        from app.services.ip_management import get_next_available_ipv4, get_next_available_ipv6

        assert get_next_available_ipv4("10.8.0.0/24") == "10.8.0.100/24"
        assert get_next_available_ipv4() == "10.0.0.100"
        assert get_next_available_ipv6("fd00::/64") == "fd00::64/64"
        assert get_next_available_ipv6() == "fd00::100"


class TestLegacyHelpersEdgeCases:
    def test_should_generate_addresses_for_generic_ipv6_subnet(self):
        from app.services.ip_management import _get_subnet_addresses

        addresses = _get_subnet_addresses("2001:db8::/64")

        assert isinstance(addresses, list)
        assert all(isinstance(address, str) for address in addresses)

    def test_should_return_input_when_incrementing_non_ipv4_string(self):
        from app.services.ip_management import _increment_ip

        assert _increment_ip("1.2.3") == "1.2.3"

    def test_should_split_cidr_only_when_prefix_present(self):
        from app.services.ip_management import cidr_to_subnet, get_cidr_to_subnet

        assert get_cidr_to_subnet("10.8.0.0/24") == "10.8.0.0"
        assert get_cidr_to_subnet("10.8.0.0") == "10.8.0.0"
        assert cidr_to_subnet("10.8.0.0") == "10.8.0.0"

    def test_should_treat_bare_ip_as_not_reserved(self):
        from app.services.ip_management import _is_reserved_ip

        assert _is_reserved_ip("10.8.0.1", "10.8.0.1") is False
        assert _is_reserved_ip("127.0.0.1", "10.8.0.1") is True

    def test_should_ignore_invalid_subnet_when_checking_reserved(self):
        from app.services.ip_management import _is_reserved_ip

        assert _is_reserved_ip("10.8.0.1", "10.8.0.0/xx") is False
        assert _is_reserved_ip("0.0.0.0", "10.8.0.0/xx") is True

    def test_should_cap_host_scan_for_ipv6_subnet(self):
        from ipaddress import ip_address

        from app.services.ip_management import _get_first_available_ip

        # Every generated host is reserved, so the safety limit stops the scan
        base = int(ip_address("fd00::"))
        reserved = [str(ip_address(base + i)) for i in range(1, 2000)]
        assert _get_first_available_ip("fd00::/64", reserved) is None
