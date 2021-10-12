import pytest

from linguard.core.models import interfaces, get_all_peers, Peer
from linguard.tests.utils import default_cleanup, is_http_success, login, create_test_iface, get_testing_app

url = "/dashboard"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    default_cleanup()


@pytest.fixture
def client():
    with get_testing_app().test_client() as client:
        yield client


def test_get(client):
    login(client)
    iface1 = create_test_iface("iface1", "10.0.0.1/24", 50000)
    iface2 = create_test_iface("iface2", "10.0.1.1/24", 50001)
    peer1 = Peer(name="peer1", description="", ipv4_address="10.0.0.2/24", nat=False, interface=iface1, dns1="8.8.8.8")
    peer2 = Peer(name="peer2", description="", ipv4_address="10.0.1.2/24", nat=False, interface=iface2, dns1="8.8.8.8")
    iface1.add_peer(peer1)
    iface2.add_peer(peer2)
    interfaces[iface1.uuid] = iface1
    interfaces[iface2.uuid] = iface2
    response = client.get(url)
    assert is_http_success(response.status_code)
    for iface in interfaces.values():
        assert iface.name.encode() in response.data
    for peer in get_all_peers().values():
        assert peer.name.encode() in response.data
