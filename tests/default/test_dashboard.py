import pytest

import system_utils
from core.config.linguard_config import config as linguard_config
from core.models import interfaces, get_all_peers, Interface
from tests.default.utils import get_default_app
from tests.utils import default_cleanup, is_http_success, login

url = "/dashboard"


def cleanup():
    default_cleanup()


@pytest.fixture
def client():
    with get_default_app().test_client() as client:
        yield client


def create_test_iface(name, ipv4, port):
    gw = list(filter(lambda i: i != "lo", system_utils.get_system_interfaces().keys()))[1]
    on_up = [
        f"{linguard_config.iptables_bin} -I FORWARD -i {name} -j ACCEPT\n" +
        f"{linguard_config.iptables_bin} -I FORWARD -o {name} -j ACCEPT\n" +
        f"{linguard_config.iptables_bin} -t nat -I POSTROUTING -o {gw} -j MASQUERADE\n"
    ]
    on_down = [
        f"{linguard_config.iptables_bin} -D FORWARD -i {name} -j ACCEPT\n" +
        f"{linguard_config.iptables_bin} -D FORWARD -o {name} -j ACCEPT\n" +
        f"{linguard_config.iptables_bin} -t nat -D POSTROUTING -o {gw} -j MASQUERADE\n"
    ]
    return Interface(name=name, gw_iface=gw, ipv4_address=ipv4, listen_port=port, auto=False, on_uu=on_up, on_down=on_down)


def test_get(client):
    login(client)
    """
    iface1 = create_test_iface("iface1", "10.0.0.1/24", 50000)
    iface2 = create_test_iface("iface1", "10.0.0.2/24", 50001)
    interfaces[iface1.uuid] = iface1
    interfaces[iface2.uuid] = iface2
    """
    response = client.get(url)
    assert is_http_success(response.status_code), cleanup()
    for sys_iface in system_utils.get_system_interfaces().keys():
        assert sys_iface.encode() in response.data, cleanup()
    for iface in interfaces.values():
        assert iface.name.encode() in response.data, cleanup()
    for peer in get_all_peers().values():
        assert peer.name.encode() in response.data, cleanup()

    cleanup()

