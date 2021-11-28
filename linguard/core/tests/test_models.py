from io import StringIO
from ipaddress import IPv4Interface

import pytest

from linguard.common.properties import global_properties
from linguard.core.exceptions import WireguardError
from linguard.core.models import Interface, Peer


@pytest.fixture(autouse=True)
def setup():
    global_properties.check_gateway_when_importing_interfaces = False
    yield


@pytest.mark.parametrize("str_conf", [
    """
    [Interface]
    PrivateKey = KMLxYphCvI4joTyrf3Dp9Yg1vLUj+b8SjLFrUeYnCk0=
    Address = 10.0.0.1/24
    PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
    ListenPort = 51820
    
    [Peer]
    PublicKey = 7NTAVIucHQJsS9Z8eT3lUV8VUoTSFrB6J272F9ox5RQ=
    AllowedIPs = 10.0.0.2/32""",
    """
    [Peer]
    PublicKey = 7NTAVIucHQJsS9Z8eT3lUV8VUoTSFrB6J272F9ox5RQ=
    AllowedIPs = 10.0.0.2/32

    [Interface]
    PrivateKey = KMLxYphCvI4joTyrf3Dp9Yg1vLUj+b8SjLFrUeYnCk0=
    Address = 10.0.0.1/24
    PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
    ListenPort = 51820
    """,
    """
    [Peer]
    PublicKey = 7NTAVIucHQJsS9Z8eT3lUV8VUoTSFrB6J272F9ox5RQ=
    AllowedIPs = 10.0.0.2/32
    
    [Interface]
    PrivateKey = KMLxYphCvI4joTyrf3Dp9Yg1vLUj+b8SjLFrUeYnCk0=
    Address = 10.0.0.1/24
    PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; 
    PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
    ListenPort = 51820
    """])
def test_import_iface_ok(str_conf: str):
    name = "test_iface"
    stream = StringIO(str_conf)
    iface = Interface.from_wireguard_conf(name, stream)
    assert iface is not None
    assert iface.name == name


@pytest.mark.parametrize("str_conf", [
    """
    [Interface]
    Address = 10.0.0.1/24
    PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
    ListenPort = 51820

    [Peer]
    PublicKey = 7NTAVIucHQJsS9Z8eT3lUV8VUoTSFrB6J272F9ox5RQ=
    AllowedIPs = 10.0.0.2/32""",
    """
    [Interface]
    PrivateKey = KMLxYphCvI4joTyrf3Dp9Yg1vLUj+b8SjLFrUeYnCk0=
    Address = 10.0.0.1/24
    PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
    ListenPort: 51820

    [Peer]
    PublicKey = 7NTAVIucHQJsS9Z8eT3lUV8VUoTSFrB6J272F9ox5RQ=
    AllowedIPs = 10.0.0.2/32""",
    """
    [Interface]
    PrivateKey = KMLxYphCvI4joTyrf3Dp9Yg1vLUj+b8SjLFrUeYnCk0=
    Address = 10.0.0.1/24
    PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
    ListenPort = 51820

    [Interface]
    PublicKey = 7NTAVIucHQJsS9Z8eT3lUV8VUoTSFrB6J272F9ox5RQ=
    AllowedIPs = 10.0.0.2/32""",
    """
    [Interface]
    PrivateKey = KMLxYphCvI4joTyrf3Dp9Yg1vLUj+b8SjLFrUeYnCk0=
    Address = 10.0.0.1/24
    PostUp = iptables -A FORWARD -i wg0 -j ACCEPT;
    PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
    ListenPort = 51820

    [Peer]
    PublicKey = 7NTAVIucHQJsS9Z8eT3lUV8VUoTSFrB6J272F9ox5RQ=
    AllowedIPs = 10.0.0.2/32"""])
def test_import_iface_ko(str_conf: str):
    name = "test_iface"
    stream = StringIO(str_conf)
    pytest.raises(WireguardError, Interface.from_wireguard_conf, name, stream)


@pytest.mark.parametrize("str_conf", [
    """
    [Interface]
    Address = 10.0.0.2/32
    PrivateKey = 7NTAVIucHQJsS9Z8eT3lUV8VUoTSFrB6J272F9ox5RQ=
    DNS = 8.8.8.8, 8.8.4.4

    [Peer]
    AllowedIPs = 0.0.0.0/0"""])
def test_import_peer_ok(str_conf: str):
    name = "test_peer"
    stream = StringIO(str_conf)
    iface = Interface(name="test_iface", listen_port=8080, ipv4_address=IPv4Interface("10.0.0.1/24"), gw_iface="eth0",
                      description="", auto=False, on_down=[], on_up=[])
    peer = Peer.from_wireguard_conf(name, stream, iface)
    assert peer is not None
    assert peer.name == name
    assert peer.ipv4_address.network == iface.ipv4_address.network
