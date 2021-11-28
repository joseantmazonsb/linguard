from ipaddress import IPv4Interface

import pytest

from linguard.common.utils.network import get_default_gateway
from linguard.common.utils.strings import list_to_str
from linguard.core.models import interfaces, Peer
from linguard.tests.utils import default_cleanup, is_http_success, login, create_test_iface, get_testing_app

url = "/wireguard/interfaces"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    default_cleanup()


@pytest.fixture
def client():
    with get_testing_app().test_client() as client:
        yield client


def test_get_edit(client):
    login(client)
    iface = create_test_iface("iface1", "10.0.0.1/24", 50000)
    peer1 = Peer(name="peer1", description="", ipv4_address=IPv4Interface("10.0.0.2/24"), nat=False, interface=iface, dns1="8.8.8.8")
    peer2 = Peer(name="peer2", description="", ipv4_address=IPv4Interface("10.0.0.3/24"), nat=False, interface=iface, dns1="8.8.8.8")
    iface.add_peer(peer1)
    iface.add_peer(peer2)
    interfaces[iface.uuid] = iface
    response = client.get(f"{url}/{iface.uuid}")
    assert is_http_success(response.status_code)
    assert iface.name.encode() in response.data
    for peer in iface.peers.values():
        assert peer.name.encode() in response.data


def test_post_edit_ok(client):
    login(client)
    iface = create_test_iface("iface1", "10.0.0.1/24", 50000)
    peer1 = Peer(name="peer1", description="", ipv4_address=IPv4Interface("10.0.0.2/24"), nat=False, interface=iface, dns1="8.8.8.8")
    peer2 = Peer(name="peer2", description="", ipv4_address=IPv4Interface("10.0.0.3/24"), nat=False, interface=iface, dns1="8.8.8.8")
    iface.add_peer(peer1)
    iface.add_peer(peer2)
    interfaces[iface.uuid] = iface

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "10.0.0.10/24", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() not in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": 40000, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() not in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": "iface2", "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() not in response.data


def test_post_edit_ko(client):
    login(client)
    iface = create_test_iface("iface1", "10.0.0.1/24", 50000)
    iface2 = create_test_iface("iface1", "10.0.1.1/24", 50000)
    peer1 = Peer(name="peer1", description="", ipv4_address=IPv4Interface("10.0.0.2/24"), nat=False, interface=iface,
                 dns1="8.8.8.8")
    peer2 = Peer(name="peer2", description="", ipv4_address=IPv4Interface("10.0.0.3/24"), nat=False, interface=iface,
                 dns1="8.8.8.8")
    iface.add_peer(peer1)
    iface.add_peer(peer2)
    interfaces[iface.uuid] = iface
    interfaces[iface2.uuid] = iface2

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "10.0.0.1023", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "10.0.0.3/24", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "10.0.0.255/24", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "10.0.1.1/24", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "aaaaa", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "10.0.0.1/38", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "10.0.0.1", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": 400000000, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": "aaaaa", "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(f"{url}/{iface.uuid}", data={
        "name": "iface&1", "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data


def test_get_add(client):
    login(client)
    response = client.get(f"{url}/add")
    assert is_http_success(response.status_code)
    assert get_default_gateway().encode() in response.data


def test_post_add_ok(client):
    login(client)
    iface = create_test_iface("iface1", "10.0.0.1/24", 50000)
    response = client.post(f"{url}/add", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert interfaces.get_value_by_attr("name", iface.name) is not None

    response = client.post(f"{url}/add", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": "10.0.0.1", "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert interfaces.get_value_by_attr("name", iface.name) is not None


def test_post_add_ko(client):
    login(client)
    iface = create_test_iface("iface1", "10.0.0.1/24", 50000)
    response = client.post(f"{url}/add", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": "not-int", "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert interfaces.get_value_by_attr("name", iface.name) is None

    response = client.post(f"{url}/add", data={
        "name": iface.name, "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": 5.00, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert interfaces.get_value_by_attr("name", iface.name) is None

    response = client.post(f"{url}/add", data={
        "name": "", "auto": iface.auto, "description": iface.description, "gateway": iface.gw_iface,
        "ipv4": iface.ipv4_address, "port": iface.listen_port, "on_up": list_to_str(iface.on_up),
        "on_down": list_to_str(iface.on_down)
    })
    assert is_http_success(response.status_code)
    assert interfaces.get_value_by_attr("name", iface.name) is None
