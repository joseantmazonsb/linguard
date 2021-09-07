import json
import os
from typing import List, Dict, Any

from core.config.linguard_config import config as linguard_config
from core.exceptions import WireguardError
from core.models import Interface, interfaces
from system_utils import run_os_command


def is_wg_iface_up(iface_name: str) -> bool:
    return run_os_command(f"sudo {linguard_config.wg_bin} show {iface_name}").successful


def generate_privkey() -> str:
    result = run_os_command(f"sudo {linguard_config.wg_bin} genkey")
    if not result.successful:
        raise WireguardError(result.err)
    return result.output


def generate_pubkey(privkey: str) -> str:
    result = run_os_command(f"echo {privkey} | sudo {linguard_config.wg_bin} pubkey")
    if not result.successful:
        raise WireguardError(result.err)
    return result.output


def get_wg_interfaces_summary(wg_bin: str, interfaces: List[Interface]) -> Dict[str, Dict[str, Any]]:
    dct = {}
    for iface in interfaces:
        if run_os_command(f"sudo {wg_bin} show {iface.name}").successful:
            status = "up"
        else:
            status = "down"
        dct[iface.name] = {
            "uuid": iface.uuid,
            "auto": iface.auto,
            "name": iface.name,
            "description": iface.description,
            "ipv4": iface.ipv4_address,
            "port": iface.listen_port,
            "status": status,
            "peers": iface.peers,
        }
    return dct


def get_wireguard_traffic() -> Dict[str, Any]:
    bin_path = os.path.join(os.path.dirname(__file__), "tools/wg-json")
    return __get_traffic__(run_os_command(bin_path).output)


def __get_traffic__(json_data: str):
    dct = {}
    for iface_name, data in json.loads(json_data).items():
        iface = interfaces.get_value_by_attr("name", iface_name)
        iface_rx = 0
        iface_tx = 0
        for peer_key, peer_data in data["peers"].items():
            peer = iface.peers.get_value_by_attr("public_key", peer_key)
            peer_rx = int(peer_data["transferRx"])/1024/1024
            peer_tx = int(peer_data["transferTx"])/1024/1024
            dct[peer.name] = {"rx": peer_rx, "tx": peer_tx}
            iface_rx += peer_rx
            iface_tx += peer_tx
        dct[iface.name] = {"rx": iface_rx, "tx": iface_tx}
    return dct


def get_wireguard_traffic_mock() -> Dict[str, Any]:
    data = """
    {"hissing-frigate":{"privateKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=","publicKey":"/TOE4TKtAqVsePRVR+5AA43HkAK5DSntkOCO7nYq5xU=","listenPort":51821,"peers":{"hWMjldxtFSuxHnNgx1hb+AXw8bOH4aO/zjaUHw5LUFY=":{"endpoint":"172.19.0.8:51822","latestHandshake":1617235493,"transferRx":34816030,"transferTx":33460010,"allowedIps":["10.0.0.2/32"]},"tPrz6gqdn7r24YkKkA39iSLb5Zo4aCFhHK5bxSpbiQ0=":{"endpoint":"172.19.0.8:51822","latestHandshake":1617235493,"transferRx":24367200,"transferTx":6004600,"allowedIps":["10.0.0.2/32"]}}},"sexy-dog":{"privateKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=","publicKey":"/TOE4TKtAqVsePRVR+5AA43HkAK5DSntkOCO7nYq5xU=","listenPort":51821,"peers":{"o0W1mjuxRVuNY+LObu8ikMOKCNnRZ4RmYw4VKtYP31o=":{"endpoint":"172.19.0.7:51823","latestHandshake":1609974495,"transferRx":9384400,"transferTx":342300,"allowedIps":["10.0.0.3/32"]},"5yD6DbtTmR7lIsGgZi4CScfeS6cSUMJqxma5hodrJBE=":{"endpoint":"172.19.0.7:51823","latestHandshake":1609974495,"transferRx":14037005,"transferTx":19462003,"allowedIps":["10.0.0.3/32"]}}}}
    """
    return __get_traffic__(data)
