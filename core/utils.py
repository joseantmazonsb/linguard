import json
import os
import random
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
            peer_rx = 0
            peer_tx = 0
            if "transferRx" in peer_data:
                peer_rx = int(peer_data["transferRx"])/1024/1024/1024
            if "transferTx" in peer_data:
                peer_tx = int(peer_data["transferTx"])/1024/1024/1024
            iface_rx += peer_rx
            iface_tx += peer_tx
            dct[peer.name] = {"rx": peer_rx, "tx": peer_tx}
        dct[iface.name] = {"rx": iface_rx, "tx": iface_tx}
    return dct


def get_wireguard_traffic_mock() -> Dict[str, Any]:
    dct = {}
    for iface in interfaces.values():
        rx = 0
        tx = 0
        for peer in iface.peers.values():
            peer_rx = random.randint(1000, 9999999999)/1024/1024/1024
            peer_tx = random.randint(1000, 9999999999)/1024/1024/1024
            dct[peer.name] = {
                "rx": peer_rx,
                "tx": peer_tx
            }
            rx += peer_rx
            tx += peer_tx
        dct[iface.name] = {
            "rx": rx,
            "tx": tx
        }
    return dct
